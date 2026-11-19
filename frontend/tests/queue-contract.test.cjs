/**
 * Hợp đồng giữa backend (người phát deep link) và frontend (người đọc chúng).
 *
 * Vì sao có bộ test này: backend từng phát `?queue=file_review` trong khi trang
 * xếp hạng chỉ nhận `FILE_REVIEW`, nên mọi nút "Kiểm tra file" mở danh sách
 * KHÔNG lọc — một deep link giả. Bug đó không thể bắt được bằng test một phía:
 * test backend chỉ so với một danh sách mã chép tay ngay trong file test, nên
 * đổi tên ở frontend là test vẫn xanh.
 *
 * Nguyên tắc: mỗi bên đọc định nghĩa THẬT của bên kia.
 *  - Ở đây (FE): đọc mã queue mà backend phát, đưa qua hàm parse thật của trang.
 *  - Ở backend (tests/test_workspace.py): đọc thẳng APPLICANT_QUEUES trong file TS.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.join(__dirname, '..');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(root, relativePath);
  const source = fs.readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}

const { APPLICANT_QUEUES, normalizeApplicantQueue, isApplicantQueue } = loadTypeScriptModule('src/lib/applicantReview.ts');

/** Queue codes as the backend actually emits them, read from its source. */
function backendQueueCodes() {
  const source = fs.readFileSync(path.join(root, '..', 'backend', 'app', 'services', 'workspace.py'), 'utf8');
  const calls = [...source.matchAll(/_applicants_target\(\s*[^,]+,\s*"([a-z_]+)"/g)].map(m => m[1]);
  assert.ok(calls.length >= 3, `expected several deep links in workspace.py, found ${calls.length}`);
  return [...new Set(calls)];
}

/** Apply the exact transform the backend applies before putting the code in a URL. */
function asUrlValue(rawCode) {
  const source = fs.readFileSync(path.join(root, '..', 'backend', 'app', 'services', 'workspace.py'), 'utf8');
  const transform = source.match(/"queue=\{queue\.([a-z]+)\(\)\}"\s*if queue/);
  assert.ok(transform, 'could not find how workspace.py formats the queue code');
  // Derived from the backend's own expression (e.g. queue.upper()), so if it
  // switches to a different casing the test follows instead of guessing.
  assert.equal(transform[1], 'upper', `workspace.py now formats the code with "${transform[1]}" — update normalizeApplicantQueue to match`);
  return rawCode.toUpperCase();
}

test('every queue code the backend emits is one the ranking page will filter on', () => {
  const codes = backendQueueCodes();
  assert.ok(codes.length >= 4, `expected the full set of queue links, got ${JSON.stringify(codes)}`);
  for (const code of codes) {
    const value = asUrlValue(code);
    assert.ok(isApplicantQueue(value),
      `backend emits ?queue=${value} but the ranking page only understands ${APPLICANT_QUEUES.join(', ')}`);
    assert.equal(normalizeApplicantQueue(value), code.toUpperCase());
  }
});

test('the backward-compatible spelling still filters, so old bookmarks are not dead links', () => {
  // The bug shipped lower-case links; anything HR bookmarked then must keep working.
  assert.equal(normalizeApplicantQueue('needs_verification'), 'NEEDS_VERIFICATION');
  assert.equal(normalizeApplicantQueue(' File_Review '), 'FILE_REVIEW');
});

test('an unknown queue code is rejected rather than silently showing everything', () => {
  assert.equal(isApplicantQueue('REVIEW_FILES'), false);
  assert.equal(isApplicantQueue(''), false);
  assert.equal(isApplicantQueue(null), false);
});
