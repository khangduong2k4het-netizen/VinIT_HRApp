/**
 * Việc của người dùng (buổi hôm nay, phiếu quá hạn) phải có link dùng được.
 *
 * Lỗi đã xảy ra thật: backend phát `target: {page: "interviews"}` trong khi
 * `workQueueListHref` đọc `target.pathname`. Kết quả là `href="undefined"` —
 * nút vẫn hiện, bấm vào thì điều hướng tới `/undefined`. Không có test nào bắt
 * được vì mọi thứ đều "đúng kiểu" ở mức TypeScript (`target` là object).
 *
 * Test này khoá đúng hợp đồng giữa server và hai hàm dựng link.
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

const { workQueueListHref, workQueueNextHref } = loadTypeScriptModule('src/lib/workQueueEntry.ts');

const ITEM = { type: 'INTERVIEW_TODAY', target: { pathname: '/interviews', search: '' }, next_application_id: null };

test('link của việc phỏng vấn trỏ tới /interviews', () => {
  assert.strictEqual(workQueueListHref(ITEM), '/interviews');
});

test('không bao giờ dựng ra "undefined" trong href', () => {
  for (const item of [
    ITEM,
    { ...ITEM, type: 'SCORECARD_OVERDUE' },
    { ...ITEM, target: { pathname: '/interviews', search: 'week=next' } },
  ]) {
    const href = workQueueListHref(item);
    assert.ok(!href.includes('undefined'), `href hỏng: ${href}`);
  }
});

test('việc không gắn hồ sơ thì không có link hồ sơ', () => {
  // Hai việc này không có `next_application_id`: chúng mở danh sách, không mở
  // một hồ sơ cụ thể. `null` ở đây là đúng, không phải thiếu dữ liệu.
  assert.strictEqual(workQueueNextHref(ITEM), null);
});

test('dạng target mới KHÔNG được là {page}', () => {
  // Nếu ai đó lại đổi backend sang `{page}` hoặc client sang `.page`, test này
  // đỏ ngay thay vì để người dùng bấm vào một nút chết.
  const broken = { target: { page: 'interviews' } };
  assert.notStrictEqual(workQueueListHref(broken), '/interviews');
});

// ---------------------------------------------------------------------------
// Nhắc hạn scorecard: hai nguồn, hai đích khác nhau
// ---------------------------------------------------------------------------

const remindersSource = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'components', 'shortlist', 'ScorecardReminders.tsx'), 'utf8');
// Cắt đúng ranh giới hàm, không cắt bằng mốc comment: cắt thô sẽ kéo theo cả
// phần JSX bên dưới và `new Function` nổ SyntaxError.
function extractFunction(source, name) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf('\n}', start) + 2;
  return source.slice(start, end);
}
const helpers = extractFunction(remindersSource, 'reminderHref') + '\n' + extractFunction(remindersSource, 'reminderKey');
const helpersJs = ts.transpileModule(helpers, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const reminderModule = { exports: {} };
new Function('module', 'exports', helpersJs + '\nmodule.exports = { reminderHref, reminderKey };')(reminderModule, reminderModule.exports);
const { reminderHref, reminderKey } = reminderModule.exports;

const SHARE_ROW = { share_id: 'S1', interview_id: null };
const INTERVIEW_ROW = { share_id: null, interview_id: 'I1' };

test('dòng nhắc của share mở đúng shortlist', () => {
  assert.strictEqual(reminderHref(SHARE_ROW), '/shortlist?share=S1');
});

test('dòng nhắc của buổi phỏng vấn KHÔNG dựng ra ?share=null', () => {
  // Lỗi thật: `share_id` là null ở nhánh buổi, và template cũ cho ra
  // `/shortlist?share=null` — nút hiện ra nhưng không mở được gì.
  const href = reminderHref(INTERVIEW_ROW);
  assert.strictEqual(href, '/interviews/I1');
  assert.ok(!href.includes('null'));
});

test('key React phân biệt hai nguồn', () => {
  // `key={r.share_id}` cũ cho ra key=null cho mọi dòng buổi phỏng vấn; nhiều
  // dòng cùng key thì React dùng lại DOM sai dòng khi danh sách đổi.
  assert.strictEqual(reminderKey(SHARE_ROW), 'share:S1');
  assert.strictEqual(reminderKey(INTERVIEW_ROW), 'interview:I1');
  assert.notStrictEqual(reminderKey(SHARE_ROW), reminderKey(INTERVIEW_ROW));
});

test('dòng thiếu cả hai thì về danh sách lịch, không có link chết', () => {
  const href = reminderHref({ share_id: null, interview_id: null });
  assert.ok(!href.includes('null') && !href.includes('undefined'), href);
});
