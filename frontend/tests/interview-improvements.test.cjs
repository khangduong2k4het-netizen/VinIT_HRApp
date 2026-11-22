/**
 * Các phần logic thuần của đợt cải tiến: kiểm giờ, .ics, câu thông báo, "còn bao lâu".
 *
 * Cùng khuôn `loadTypeScriptModule` với các test khác trong repo.
 */
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(__dirname, '..', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}

const { vietnamLocalToUtc, validateInterviewForm } = loadTypeScriptModule('src/lib/interviewTime.ts');
const { buildInterviewIcs, icsStamp, icsEscape, icsFold } = loadTypeScriptModule('src/lib/interviewIcs.ts');
const { countdownLabel } = loadTypeScriptModule('src/lib/relativeTime.ts');
const { notificationText, shortVietnamTime } = loadTypeScriptModule('src/lib/notificationText.ts');

// ---------------------------------------------------------------------------
// Kiểm giờ — 3.2
// ---------------------------------------------------------------------------

test('giờ Việt Nam hợp lệ thành ISO có offset', () => {
  assert.strictEqual(vietnamLocalToUtc('2026-12-01T14:00'), '2026-12-01T14:00:00+07:00');
});

test('chuỗi rỗng không sinh ra "+07:00" trần', () => {
  // Lỗi cũ: nối thẳng hậu tố nên "abc" thành "abc+07:00" và máy chủ trả 422
  // "value is not a valid datetime" — không nói ô nào sai.
  assert.strictEqual(vietnamLocalToUtc(''), null);
  assert.strictEqual(vietnamLocalToUtc('abc'), null);
  assert.strictEqual(vietnamLocalToUtc('14:00'), null);
});

test('ngày không tồn tại bị loại, không bị tự sửa', () => {
  // `new Date('2026-02-30')` tự chuyển thành 2/3. Kiểm mẫu + so lại ngày để chặn.
  assert.strictEqual(vietnamLocalToUtc('2026-02-30T09:00'), null);
  assert.strictEqual(vietnamLocalToUtc('2026-13-01T09:00'), null);
  assert.strictEqual(vietnamLocalToUtc('2026-12-01T25:00'), null);
});

test('ngày nhuận hợp lệ vẫn qua', () => {
  assert.strictEqual(vietnamLocalToUtc('2028-02-29T09:00'), '2028-02-29T09:00:00+07:00');
});

test('validate: giờ kết thúc phải sau bắt đầu', () => {
  const base = { startsAt: '2026-12-01T14:00', endsAt: '2026-12-01T15:00', locationKind: 'ONSITE', locationText: '', reviewerCount: 1 };
  assert.strictEqual(validateInterviewForm(base), null);
  assert.match(validateInterviewForm({ ...base, endsAt: '2026-12-01T13:00' }), /Kết thúc/);
  assert.match(validateInterviewForm({ ...base, endsAt: base.startsAt }), /Kết thúc/);
});

test('validate: online/điện thoại cần link', () => {
  const base = { startsAt: '2026-12-01T14:00', endsAt: '2026-12-01T15:00', locationKind: 'ONLINE', locationText: '  ', reviewerCount: 1 };
  assert.match(validateInterviewForm(base), /link/);
  assert.strictEqual(validateInterviewForm({ ...base, locationText: 'https://meet/x' }), null);
});

test('validate: phải có người phỏng vấn', () => {
  const base = { startsAt: '2026-12-01T14:00', endsAt: '2026-12-01T15:00', locationKind: 'ONSITE', locationText: '', reviewerCount: 0 };
  assert.match(validateInterviewForm(base), /người phỏng vấn/);
});

// ---------------------------------------------------------------------------
// .ics — 4.1
// ---------------------------------------------------------------------------

const INTERVIEW = {
  interview_id: '11111111-2222-3333-4444-555555555555', application_id: 'a',
  round_number: 2, status: 'SCHEDULED',
  starts_at: '2026-12-01T07:00:00+00:00', ends_at: '2026-12-01T08:00:00+00:00',
  location_kind: 'ONSITE', location_text: 'Phòng 3A',
  participant_count: 2, submitted_scorecards: 0, total_scorecards: 0,
  candidate_name: 'Nguyễn Thị Ứng Viên', position_code: 'IT-0001',
};

test('giờ trong .ics là UTC, đúng RFC', () => {
  assert.strictEqual(icsStamp('2026-12-01T07:00:00+00:00'), '20261201T070000Z');
});

test('.ics dùng CRLF — Apple Calendar từ chối file chỉ có LF', () => {
  const ics = buildInterviewIcs(INTERVIEW, new Date('2026-11-30T00:00:00Z'));
  assert.ok(ics.includes('\r\n'), 'phải có CRLF');
  assert.ok(!/[^\r]\n/.test(ics), 'không được có LF trần');
  assert.ok(ics.endsWith('\r\n'));
});

test('.ics có UID ổn định theo buổi', () => {
  // Nhập lại cùng buổi thì ứng dụng lịch cập nhật thay vì tạo bản trùng.
  const a = buildInterviewIcs(INTERVIEW, new Date('2026-11-30T00:00:00Z'));
  const b = buildInterviewIcs(INTERVIEW, new Date('2026-12-01T00:00:00Z'));
  const uid = line => line.split('\r\n').find(l => l.startsWith('UID:'));
  assert.strictEqual(uid(a), uid(b));
  assert.ok(uid(a).includes(INTERVIEW.interview_id));
});

test('ký tự đặc biệt trong tên được escape', () => {
  assert.strictEqual(icsEscape('a,b;c\\d\ne'), 'a\\,b\\;c\\\\d\\ne');
  const ics = buildInterviewIcs({ ...INTERVIEW, candidate_name: 'Lê, Văn; A' }, new Date());
  assert.ok(ics.includes('Lê\\, Văn\\; A'));
});

test('dòng dài được gấp ở 75 octet, không cắt giữa ký tự', () => {
  const long = 'Nguyễn ' + 'ệ'.repeat(80);
  const folded = icsFold(long);
  for (const line of folded.split('\r\n')) {
    assert.ok(Buffer.byteLength(line, 'utf8') <= 75, `dòng quá dài: ${Buffer.byteLength(line)}`);
  }
  // Ghép lại (bỏ khoảng trắng nối dòng) phải ra chuỗi gốc — nếu cắt giữa một ký
  // tự nhiều byte thì bước này sẽ hỏng.
  const joined = folded.replace(/\r\n /g, '');
  assert.strictEqual(joined, long);
});

test('.ics có đủ DTSTART/DTEND/SUMMARY', () => {
  const ics = buildInterviewIcs(INTERVIEW, new Date('2026-11-30T00:00:00Z'));
  for (const key of ['BEGIN:VCALENDAR', 'BEGIN:VEVENT', 'DTSTART:20261201T070000Z',
                     'DTEND:20261201T080000Z', 'SUMMARY:', 'END:VEVENT', 'END:VCALENDAR']) {
    assert.ok(ics.includes(key), `thiếu ${key}`);
  }
});

// ---------------------------------------------------------------------------
// "Còn bao lâu" — 4.2
// ---------------------------------------------------------------------------

test('khoảng cách dễ đọc trong ngày', () => {
  const now = new Date('2026-12-01T06:00:00Z');
  assert.strictEqual(countdownLabel('2026-12-01T08:00:00Z', now), 'Còn 2 giờ');
  assert.strictEqual(countdownLabel('2026-12-01T06:15:00Z', now), 'Còn 15 phút');
  assert.strictEqual(countdownLabel('2026-12-01T06:02:00Z', now), 'Sắp bắt đầu');
});

test('không hiện khoảng cách cho buổi đã qua hoặc quá xa', () => {
  const now = new Date('2026-12-01T06:00:00Z');
  assert.strictEqual(countdownLabel('2026-12-01T05:00:00Z', now), null);
  assert.strictEqual(countdownLabel('2027-06-01T06:00:00Z', now), null);
});

// ---------------------------------------------------------------------------
// Câu thông báo — 1.3
// ---------------------------------------------------------------------------

test('câu thông báo nói được giờ ĐÃ ĐỔI, không chỉ "vừa cập nhật"', () => {
  const text = notificationText({
    kind: 'INTERVIEW_UPDATED', round_number: 2, starts_at: '2026-12-01T08:30:00Z',
    payload: { starts_at_from: '2026-12-01T07:00:00Z', starts_at_to: '2026-12-01T08:30:00Z' },
  });
  assert.match(text, /Lịch phỏng vấn đã thay đổi/);
  assert.match(text, /→/);
  // 07:00Z = 14:00 VN, 08:30Z = 15:30 VN
  assert.ok(text.includes('14:00'), text);
  assert.ok(text.includes('15:30'), text);
});

test('sửa mỗi phòng họp thì không hiện 14:00 → 14:00', () => {
  const text = notificationText({
    kind: 'INTERVIEW_UPDATED', round_number: 2, starts_at: '2026-12-01T07:00:00Z',
    payload: { starts_at_from: '2026-12-01T07:00:00Z', starts_at_to: '2026-12-01T07:00:00Z' },
  });
  assert.ok(!text.includes('→'), text);
});

test('loại thông báo lạ không hiện "undefined"', () => {
  const text = notificationText({ kind: 'SOMETHING_NEW', round_number: 1, starts_at: null, payload: {} });
  assert.ok(!text.includes('undefined'), text);
  assert.ok(text.length > 0);
});

test('giờ hiển thị theo Việt Nam, không theo UTC của máy chủ', () => {
  // 07:00Z = 14:00 giờ Việt Nam.
  assert.ok(shortVietnamTime('2026-12-01T07:00:00Z').includes('14:00'));
});
