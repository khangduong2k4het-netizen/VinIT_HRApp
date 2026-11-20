const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
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

const {
  snapshotWorkQueue, increasesSince, totalNewWork, readWorkQueueSnapshot, writeWorkQueueSnapshot,
  WORK_QUEUE_SNAPSHOT_KEY, WORK_QUEUE_BASELINE_MAX_AGE_MS,
} = loadTypeScriptModule('src/lib/workQueueDigest.ts');

function fakeStorage(initial) {
  const data = new Map(initial ? [[WORK_QUEUE_SNAPSHOT_KEY, initial]] : []);
  return {
    data,
    getItem: key => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => { data.set(key, value); },
  };
}

const item = (id, count, type = 'NEEDS_VERIFICATION', title = 'Vị trí A') => ({
  item_id: id, count, type, position_title: title,
});

const T0 = Date.UTC(2026, 10, 19, 8, 0, 0);

test('số việc tăng so với lần trước được báo, kèm phần tăng thêm', () => {
  const previous = snapshotWorkQueue([item('NEEDS_VERIFICATION:p1', 4), item('FILE_REVIEW:p1', 2)], T0);
  const increases = increasesSince(previous, [
    item('NEEDS_VERIFICATION:p1', 6),
    item('FILE_REVIEW:p1', 2), // không đổi: không phải tin mới
  ], T0 + 60_000);

  assert.equal(increases.length, 1);
  assert.equal(increases[0].itemId, 'NEEDS_VERIFICATION:p1');
  assert.equal(increases[0].added, 2);
  assert.equal(increases[0].type, 'NEEDS_VERIFICATION');
  assert.equal(totalNewWork(increases), 2);
});

test('dòng việc mới xuất hiện được tính toàn bộ, dòng giảm hoặc biến mất thì bỏ qua', () => {
  const previous = snapshotWorkQueue([item('NEEDS_VERIFICATION:p1', 5), item('FILE_REVIEW:p1', 3)], T0);
  const increases = increasesSince(previous, [
    item('NEEDS_VERIFICATION:p1', 2), // HR đã xử lý bớt
    item('DUPLICATE_PENDING:p1', 1), // nhóm việc mới
  ], T0 + 60_000);

  assert.deepEqual(increases.map(entry => [entry.itemId, entry.added]), [['DUPLICATE_PENDING:p1', 1]]);
});

test('lần đầu mở dashboard thì chưa có gì để so', () => {
  assert.deepEqual(increasesSince(null, [item('NEEDS_VERIFICATION:p1', 9)], T0), []);
});

test('mốc quá cũ không còn là "lần trước"', () => {
  const previous = snapshotWorkQueue([item('NEEDS_VERIFICATION:p1', 4)], T0);
  const later = T0 + WORK_QUEUE_BASELINE_MAX_AGE_MS + 1;
  assert.deepEqual(increasesSince(previous, [item('NEEDS_VERIFICATION:p1', 40)], later), []);
  // Đúng ngưỡng vẫn còn dùng được.
  assert.equal(increasesSince(previous, [item('NEEDS_VERIFICATION:p1', 5)], T0 + WORK_QUEUE_BASELINE_MAX_AGE_MS).length, 1);
});

test('chụp và đọc lại mốc, dữ liệu hỏng bị bỏ qua thay vì dựng số sai', () => {
  const storage = fakeStorage();
  const snapshot = snapshotWorkQueue([item('NEEDS_VERIFICATION:p1', 7)], T0);
  writeWorkQueueSnapshot(snapshot, storage);
  assert.deepEqual(readWorkQueueSnapshot(storage), snapshot);

  assert.equal(readWorkQueueSnapshot(fakeStorage('{not json')), null);
  assert.equal(readWorkQueueSnapshot(fakeStorage('{"takenAt":"x","counts":{}}')), null);
  assert.equal(readWorkQueueSnapshot(fakeStorage('{"takenAt":1}')), null);
  const cleaned = readWorkQueueSnapshot(fakeStorage('{"takenAt":1,"counts":{"a":2,"b":-1,"c":"x"}}'));
  assert.deepEqual(cleaned, { takenAt: 1, counts: { a: 2 } }, 'chỉ giữ số việc hợp lệ');
});

test('storage bị chặn không làm hỏng dashboard', () => {
  const throwing = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.equal(readWorkQueueSnapshot(throwing), null);
  assert.doesNotThrow(() => writeWorkQueueSnapshot({ takenAt: T0, counts: {} }, throwing));
});
