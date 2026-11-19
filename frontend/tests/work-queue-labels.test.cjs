const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

// Nạp module TS vào bộ nhớ. `shims` cho phép thay một import (ví dụ ./en.json)
// bằng giá trị thật, vì Node không require được file .json qua đường này.
function loadTypeScriptModule(relativePath, shims = {}) {
  const filename = path.join(__dirname, '..', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
    fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  const localRequire = id => (id in shims ? shims[id] : require(id));
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, localRequire);
  return loaded.exports;
}

const labels = loadTypeScriptModule('src/lib/workQueueLabels.ts');
const english = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'src/i18n/en.json'), 'utf8'));
const { translate } = loadTypeScriptModule('src/i18n/translate.ts', { './en.json': { __esModule: true, default: english } });

const t = (key, ...args) => translate(key, 'vi', ...args);

test('deadline items get their own wording instead of a shared generic label', () => {
  assert.equal(labels.workQueueTypeLabel({ type: 'POSITION_DEADLINE_PASSED' }), 'Vị trí đã quá hạn ứng tuyển');
  assert.equal(labels.workQueueTypeLabel({ type: 'POSITION_DEADLINE_SOON' }), 'Vị trí sắp hết hạn ứng tuyển');
  assert.equal(labels.workQueueTypeAction({ type: 'POSITION_DEADLINE_PASSED' }), 'Xem vị trí');
});

test('a type this build does not know never renders as undefined', () => {
  // Backend deploy trước frontend: loại việc mới phải hiện chữ trung tính.
  assert.equal(labels.workQueueTypeLabel({ type: 'SOMETHING_NEW' }), 'Việc cần xử lý');
  assert.equal(labels.workQueueTypeAction({ type: 'SOMETHING_NEW' }), 'Mở');
  assert.doesNotMatch(labels.workQueueTypeLabel({ type: 'SOMETHING_NEW' }), /undefined/);
});

test('deadline note counts down and switches to overdue past zero', () => {
  assert.equal(labels.deadlineNote({ days_left: 3 }, t), 'Còn 3 ngày tới hạn');
  assert.equal(labels.deadlineNote({ days_left: 0 }, t), 'Hạn chót là hôm nay');
  assert.equal(labels.deadlineNote({ days_left: -2 }, t), 'Đã quá hạn 2 ngày');
  // Việc không gắn với hạn chót thì không được bịa ra "còn 0 ngày".
  assert.equal(labels.deadlineNote({}, t), null);
  assert.equal(labels.deadlineNote({ days_left: null }, t), null);
});

test('every new message has an English translation', () => {
  for (const key of [
    'Đã quá hạn {0} ngày',
    'Hạn chót là hôm nay',
    'Còn {0} ngày tới hạn',
    'Vị trí đã quá hạn ứng tuyển',
    'Vị trí sắp hết hạn ứng tuyển',
    'Việc cần xử lý',
    'Mở',
    '{0} hồ sơ chờ quá 7 ngày · lâu nhất {1} ngày',
    '{0} vị trí đã quá hạn, không nhận hồ sơ',
  ]) {
    assert.notEqual(translate(key, 'en'), key, `thiếu bản dịch: ${key}`);
  }
});
