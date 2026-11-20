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

const { interpretGenerationFailure } = loadTypeScriptModule('src/lib/criteriaGeneration.ts');

const withDetail = (detail, status = 502) => ({ response: { status, data: { detail } } });

test('backend trả detail: lỗi thật, được thử lại và hiện nguyên văn', () => {
  const outcome = interpretGenerationFailure(withDetail('AI trả về bộ tiêu chí không hợp lệ. Vui lòng thử lại.'), false);
  assert.equal(outcome.action, 'retry');
  assert.equal(outcome.kind, 'server');
  assert.match(outcome.detail, /không hợp lệ/);
});

test('response không có detail (proxy cắt, HTML, 500 plain text) là opaque, không phải lỗi AI', () => {
  // Đây chính là trường hợp đã gặp: popup hiện câu dự phòng vì body không có detail.
  for (const data of [undefined, null, '', 'Internal Server Error', '<html>504</html>', { message: 'x' }]) {
    const outcome = interpretGenerationFailure({ response: { status: 504, data } }, false);
    assert.equal(outcome.action, 'retry');
    assert.equal(outcome.kind, 'opaque');
    assert.equal(outcome.detail, '');
  }
});

test('nhưng nếu kiểm tra lại thấy tiêu chí đã có thì coi là thành công', () => {
  // Request bị cắt giữa đường trong khi backend vẫn chạy xong: không được báo
  // "chưa tạo được" và không được bắt HR làm lại.
  for (const data of [undefined, { message: 'x' }, { detail: 'AI trả về bộ tiêu chí không hợp lệ.' }]) {
    assert.deepEqual(interpretGenerationFailure({ response: { status: 504, data } }, true), { action: 'verified' });
  }
});

test('không có response và không kiểm tra được là unknown, không khẳng định thất bại', () => {
  assert.deepEqual(interpretGenerationFailure({ message: 'Network Error' }, null), { action: 'unknown', kind: 'network' });
});

test('không kiểm tra được nhưng backend có nói lý do thì vẫn dùng lý do đó', () => {
  const outcome = interpretGenerationFailure(withDetail('Không thể tạo tiêu chí bằng AI. Vui lòng kiểm tra cấu hình và thử lại.', 503), null);
  assert.equal(outcome.action, 'retry');
  assert.equal(outcome.kind, 'server');
  assert.match(outcome.detail, /cấu hình/);
});

test('lỗi không có response và kiểm tra lại chắc chắn chưa có tiêu chí thì thử lại', () => {
  assert.deepEqual(interpretGenerationFailure({ message: 'Network Error' }, false), {
    action: 'retry', kind: 'network', detail: '',
  });
});
