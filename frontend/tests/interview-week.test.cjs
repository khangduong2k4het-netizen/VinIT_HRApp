/**
 * Tuần của "Lịch của tôi" — logic ở `src/lib/interviewWeek.ts`.
 *
 * Ba nhóm, mỗi nhóm một lỗi thật có thể xảy ra:
 * 1. Tuần bắt đầu thứ Hai (Chủ nhật thuộc tuần ĐÃ QUA).
 * 2. Cộng ngày qua tháng/năm, không sửa đối tượng gốc.
 * 3. Gom nhóm theo ngày VIỆT NAM, không theo ngày UTC.
 */
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

// Cùng cách nạp với tests/careers-filter.test.cjs: dùng chính `typescript` của
// repo để chuyển TS -> CJS. Tự viết regex chuyển đổi là cách chắc chắn để test
// hỏng mỗi lần thêm một chú thích kiểu.
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

const { mondayOf, addDays, vietnamDayKey } = loadTypeScriptModule('src/lib/interviewWeek.ts');

test('thứ Hai trả về chính nó', () => {
  const monday = new Date(Date.UTC(2026, 11, 7));   // 2026-12-07 là thứ Hai
  assert.strictEqual(mondayOf(monday).toISOString(), monday.toISOString());
});

test('giữa tuần lùi về thứ Hai', () => {
  const thursday = new Date(Date.UTC(2026, 11, 10));
  assert.strictEqual(mondayOf(thursday).toISOString(), new Date(Date.UTC(2026, 11, 7)).toISOString());
});

test('Chủ nhật thuộc tuần ĐÃ QUA, không phải tuần mới', () => {
  // Lỗi kinh điển: getUTCDay() trả 0 cho Chủ nhật, công thức "weekday - 1" đẩy
  // nó sang TUẦN SAU. Đây chính là ca mà test này canh.
  const sunday = new Date(Date.UTC(2026, 11, 13));
  assert.strictEqual(mondayOf(sunday).toISOString(), new Date(Date.UTC(2026, 11, 7)).toISOString());
});

test('qua năm vẫn đúng', () => {
  assert.strictEqual(mondayOf(new Date(Date.UTC(2027, 0, 1))).toISOString(),
                     new Date(Date.UTC(2026, 11, 28)).toISOString());
});

test('addDays giữ nguyên giờ trong ngày', () => {
  const base = new Date(Date.UTC(2026, 11, 28, 3, 17));
  assert.strictEqual(addDays(base, 7).toISOString(), new Date(Date.UTC(2027, 0, 4, 3, 17)).toISOString());
});

test('addDays âm lùi đúng', () => {
  assert.strictEqual(addDays(new Date(Date.UTC(2026, 0, 1)), -1).toISOString(),
                     new Date(Date.UTC(2025, 11, 31)).toISOString());
});

test('addDays không sửa đối tượng gốc', () => {
  const base = new Date(Date.UTC(2026, 11, 7));
  addDays(base, 3);
  assert.strictEqual(base.toISOString(), new Date(Date.UTC(2026, 11, 7)).toISOString());
});

test('23:00 UTC là NGÀY HÔM SAU ở Việt Nam', () => {
  // Đây là ca làm hỏng "Lịch của tôi" nếu gom theo ngày UTC: buổi tối hôm trước
  // trong DB lại hiện ở ngày hôm trước trên lịch, trong khi người dùng ở Việt
  // Nam phải đi phỏng vấn 06:00 sáng hôm sau.
  assert.strictEqual(vietnamDayKey('2026-12-07T23:00:00.000Z'), '2026-12-08');
});

test('06:00 giờ Việt Nam vẫn là ngày đó', () => {
  assert.strictEqual(vietnamDayKey('2026-12-08T06:00:00.000Z'), '2026-12-08');
});

test('00:30 giờ Việt Nam thuộc ngày mới', () => {
  // 17:30Z hôm trước = 00:30 hôm sau giờ Việt Nam.
  assert.strictEqual(vietnamDayKey('2026-12-07T17:30:00.000Z'), '2026-12-08');
});
