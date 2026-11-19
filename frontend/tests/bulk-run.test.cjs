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

const run = loadTypeScriptModule('src/lib/bulkActionRun.ts');
const {
  bulkSteps, createBulkRun, remainingSteps, retryFailed, bulkRunProgress, stopPoint,
} = run;

test('shortlist only plans transitions the state machine allows', () => {
  // Hồ sơ Mới phải đi hai bước; Đang xem đi một bước; đã Shortlist không có bước.
  assert.deepEqual(bulkSteps('shortlist', 'NEW'), ['IN_REVIEW', 'SHORTLIST']);
  assert.deepEqual(bulkSteps('shortlist', 'IN_REVIEW'), ['SHORTLIST']);
  assert.deepEqual(bulkSteps('shortlist', 'SHORTLIST'), []);
  // Loại là một bước cho mọi hồ sơ còn trong sàng lọc, và không có bước nào nếu
  // hồ sơ đã bị loại (không lặp lại một quyết định đã ghi).
  assert.deepEqual(bulkSteps('reject', 'NEW'), ['REJECTED_SCREENING']);
  assert.deepEqual(bulkSteps('reject', 'SHORTLIST'), ['REJECTED_SCREENING']);
  assert.deepEqual(bulkSteps('reject', 'REJECTED_SCREENING'), []);
});

test('a row with no valid step never enters the batch', () => {
  const rows = createBulkRun([
    { application_id: 'a1', candidate_name: '  Lê Thu Hà ', application_status: 'IN_REVIEW' },
    { application_id: 'a2', candidate_name: null, application_status: 'SHORTLIST' },
    { application_id: 'a3', application_status: 'NEW' },
  ], 'shortlist');
  assert.deepEqual(rows.map(row => row.application_id), ['a1', 'a3']);
  assert.equal(rows[0].candidate_name, 'Lê Thu Hà');
  assert.equal(rows[0].state, 'pending');
  assert.equal(rows[0].applied, 0);
  assert.equal(rows[0].reached_status, null);
});

test('retry resets only the failed rows and resumes at the missing step', () => {
  const rows = createBulkRun([
    { application_id: 'done', candidate_name: 'Xong', application_status: 'IN_REVIEW' },
    { application_id: 'half', candidate_name: 'Dở', application_status: 'NEW' },
    { application_id: 'fresh', candidate_name: 'Chưa chạy', application_status: 'IN_REVIEW' },
  ], 'shortlist');
  // Hồ sơ đã xong, hồ sơ dừng sau bước Mới → Đang xem, hồ sơ lỗi ngay bước đầu.
  const finished = [
    { ...rows[0], state: 'done', applied: 1, reached_status: 'SHORTLIST' },
    { ...rows[1], state: 'failed', applied: 1, reached_status: 'IN_REVIEW', error: 'Máy chủ bận' },
    { ...rows[2], state: 'failed', applied: 0, reached_status: null, error: 'Hết thời gian chờ' },
  ];
  const retried = retryFailed(finished);
  assert.equal(retried[0].state, 'done', 'a finished row is never re-run');
  assert.equal(retried[0].applied, 1);
  assert.equal(retried[1].state, 'pending');
  assert.equal(retried[1].error, null);
  assert.equal(retried[2].state, 'pending');
  // Chỉ phần còn thiếu được gọi: bước đã ghi không lặp lại trong lịch sử hồ sơ.
  assert.deepEqual(remainingSteps(retried[1]), ['SHORTLIST']);
  assert.deepEqual(remainingSteps(retried[2]), ['SHORTLIST']);
  // Lần chạy lại đúng bằng tập lỗi, không phải cả lô.
  assert.deepEqual(retried.filter(row => row.state === 'pending').map(row => row.application_id), ['half', 'fresh']);
});

test('the stop point names the last written step and the missing target', () => {
  const [row] = createBulkRun([{ application_id: 'a1', candidate_name: 'Dở', application_status: 'NEW' }], 'shortlist');
  assert.equal(stopPoint({ ...row, state: 'failed', applied: 0, error: 'x' }), null, 'nothing written yet means no stop point');
  assert.deepEqual(
    stopPoint({ ...row, state: 'failed', applied: 1, reached_status: 'IN_REVIEW', error: 'x' }),
    { reached: 'IN_REVIEW', target: 'SHORTLIST' },
  );
  // Một hồ sơ đã xong không phải chỗ dừng, kể cả khi nó từng lỗi ở lần trước.
  assert.equal(stopPoint({ ...row, state: 'done', applied: 2, reached_status: 'SHORTLIST', error: null }), null);
});

test('progress counts every row exactly once', () => {
  const rows = createBulkRun([
    { application_id: 'a1', application_status: 'IN_REVIEW' },
    { application_id: 'a2', application_status: 'IN_REVIEW' },
    { application_id: 'a3', application_status: 'NEW' },
  ], 'reject');
  const progress = bulkRunProgress([
    { ...rows[0], state: 'done' },
    { ...rows[1], state: 'failed', error: 'lỗi' },
    rows[2],
  ]);
  assert.deepEqual(progress, { total: 3, done: 1, failed: 1, pending: 1, running: 0, finished: 2 });
  assert.deepEqual(bulkRunProgress([]), { total: 0, done: 0, failed: 0, pending: 0, running: 0, finished: 0 });
});
