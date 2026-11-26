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

const { duplicateCompareHref, pairSignal, differingOutcomes } = loadTypeScriptModule('src/lib/duplicateCompare.ts');

test('đường dẫn so sánh mang theo đúng cặp đang xem', () => {
  assert.equal(
    duplicateCompareHref('p1', 'app-3', 'app-9'),
    '/positions/p1/applicants/compare?left=app-3&right=app-9',
  );
  // Mã có ký tự đặc biệt không được làm vỡ URL.
  assert.match(duplicateCompareHref('p1', 'a b', 'c&d'), /left=a\+b&right=c%26d$/);
});

test('tìm tín hiệu của đúng cặp, không phụ thuộc thứ tự hai bên', () => {
  const signals = [
    { signal_id: 's1', application_id_1: 'app-1', application_id_2: 'app-2' },
    { signal_id: 's2', application_id_1: 'app-9', application_id_2: 'app-3' },
  ];
  assert.equal(pairSignal(signals, 'app-3', 'app-9')?.signal_id, 's2', 'bảng tín hiệu có thể ghi ngược thứ tự');
  assert.equal(pairSignal(signals, 'app-2', 'app-1')?.signal_id, 's1');
  assert.equal(pairSignal(signals, 'app-3', 'app-4'), undefined);
  assert.equal(pairSignal(signals, null, 'app-9'), undefined);
});

test('chỉ đếm tiêu chí có ở cả hai bên và kết luận khác nhau', () => {
  const left = [
    { criterion_id: 'c1', outcome: 'MATCH' },
    { criterion_id: 'c2', outcome: 'UNCLEAR' },
    { criterion_id: 'c3', outcome: 'MATCH' },
  ];
  const right = [
    { criterion_id: 'c1', outcome: 'STRONG_MATCH' },
    { criterion_id: 'c2', outcome: 'UNCLEAR' },
    { criterion_id: 'c4', outcome: 'NO_MATCH' },
  ];
  assert.deepEqual(differingOutcomes(left, right), ['c1'], 'c3 chỉ có một bên, c4 chỉ có một bên');
  assert.deepEqual(differingOutcomes(left, left), []);
});
