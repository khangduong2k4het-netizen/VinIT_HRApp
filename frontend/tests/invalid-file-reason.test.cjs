const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(__dirname, '..', relativePath);
  const source = fs.readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}

const { explainInvalidFile } = loadTypeScriptModule('src/lib/invalidFileReason.ts');

test('machine codes from the upload path are translated', () => {
  assert.equal(explainInvalidFile('FILE_TOO_LARGE'), 'TOO_LARGE');
  assert.equal(explainInvalidFile('File cv.pdf is empty or exceeds the size limit'), 'TOO_LARGE');
});

test('the validator sentence for a wrong file type is recognised', () => {
  assert.equal(explainInvalidFile('File bad.pdf is not a valid PDF or DOCX'), 'NOT_PDF_OR_DOCX');
  assert.equal(explainInvalidFile('Unsupported document type'), 'NOT_PDF_OR_DOCX');
});

test('an unknown reason stays unknown instead of guessing', () => {
  // Guessing a cause is worse than admitting we do not know: HR would go and
  // "fix" the wrong thing.
  assert.equal(explainInvalidFile('SOMETHING_NEW'), 'UNKNOWN');
  assert.equal(explainInvalidFile(null), 'UNKNOWN');
  assert.equal(explainInvalidFile(''), 'UNKNOWN');
});
