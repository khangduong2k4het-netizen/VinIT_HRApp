const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const filename = path.join(__dirname, '../src/lib/syntheticIntake.ts');
const js = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const loaded = new Module(filename, module); loaded.filename = filename; loaded.paths = Module._nodeModulePaths(path.dirname(filename)); loaded._compile(js, filename);
const { careersFailure } = loaded.exports;

test('unknown submission outcome retains the same request and warns against resubmitting changed data', () => {
  assert.match(careersFailure(null, null), /Giữ nguyên toàn bộ form/);
  assert.match(careersFailure(409, 'Mã yêu cầu đã được sử dụng cho nội dung khác'), /nội dung khác/);
  assert.match(careersFailure(503, 'Storage'), /Giữ nguyên form/);
  assert.match(careersFailure(422, [{ msg: 'invalid' }]), /chưa hợp lệ/);
});
