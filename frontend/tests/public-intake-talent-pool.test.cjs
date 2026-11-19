const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function load(relativePath) {
  const filename = path.join(__dirname, '..', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}

const { failureFromStatus, MAX_FILE_BYTES, validateCv } = load('src/lib/publicApply.ts');
const { poolRef, scanIsActive, scoreText, SKIP_REASONS } = load('src/lib/talentPool.ts');

test('validateCv checks presence, extension and max file size', () => {
  assert.equal(validateCv(null), 'MISSING');
  assert.equal(validateCv({ name: 'resume.exe', size: 100 }), 'TYPE');
  assert.equal(validateCv({ name: 'CV.PDF', size: MAX_FILE_BYTES + 1 }), 'SIZE');
  assert.equal(validateCv({ name: 'candidate.docx', size: 50_000 }), null);
  assert.equal(validateCv({ name: 'scan.PNG', size: 50_000 }), null);
});

test('failureFromStatus maps HTTP statuses to stable public error codes', () => {
  assert.equal(failureFromStatus(429), 'RATE_LIMIT');
  assert.equal(failureFromStatus(503), 'UNAVAILABLE');
  assert.equal(failureFromStatus(404), 'POSITION_CLOSED');
  assert.equal(failureFromStatus(413), 'FILE');
  assert.equal(failureFromStatus(400), 'FILE');
  assert.equal(failureFromStatus(500), 'NETWORK');
});

test('talentPool helpers format opaque refs, scores and active scan states', () => {
  assert.equal(poolRef('a1b2c3d4-e5f6-7890-1234-567890abcdef'), '#A1B2C3D4');
  assert.equal(scoreText(null), '—');
  assert.equal(scoreText(87.64), '87.6%');
  assert.equal(scanIsActive('PENDING'), true);
  assert.equal(scanIsActive('PROCESSING'), true);
  assert.equal(scanIsActive('COMPLETED'), false);
  assert.equal(scanIsActive('FAILED'), false);
  assert.ok(SKIP_REASONS.DUPLICATE_PHONE);
});
