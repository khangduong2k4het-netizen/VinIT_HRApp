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

const { suggestFinishStatus, SHORTLIST_MIN_SCORE } = loadTypeScriptModule('src/lib/finishSuggestion.ts');

test('đang xem và điểm đạt ngưỡng thì chọn sẵn Shortlist', () => {
  const suggestion = suggestFinishStatus({
    currentStatus: 'IN_REVIEW',
    nextStatuses: ['SHORTLIST', 'REJECTED_SCREENING'],
    mandatoryFailed: false,
    score: 69,
  });
  assert.deepEqual(suggestion, { status: 'SHORTLIST', reason: 'READY_FOR_SHORTLIST' });
  assert.equal(SHORTLIST_MIN_SCORE, 60);
});

test('trượt tiêu chí bắt buộc thì đề xuất loại, kể cả khi điểm cao', () => {
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'IN_REVIEW', nextStatuses: ['SHORTLIST', 'REJECTED_SCREENING'], mandatoryFailed: true, score: 95 }),
    { status: 'REJECTED_SCREENING', reason: 'MANDATORY_FAILED' },
  );
});

test('hồ sơ mới thì đề xuất chuyển sang Đang xem, không nhảy thẳng Shortlist', () => {
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'NEW', nextStatuses: ['IN_REVIEW', 'REJECTED_SCREENING'], mandatoryFailed: false, score: 88 }),
    { status: 'IN_REVIEW', reason: 'START_REVIEW' },
  );
});

test('đã shortlist thì đề xuất bước kế tiếp là phỏng vấn', () => {
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'SHORTLIST', nextStatuses: ['IN_REVIEW', 'INTERVIEW', 'REJECTED_SCREENING'], mandatoryFailed: false, score: 88 }),
    { status: 'INTERVIEW', reason: 'ADVANCE_STAGE' },
  );
});

test('điểm dưới ngưỡng thì không đề xuất shortlist', () => {
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'IN_REVIEW', nextStatuses: ['SHORTLIST', 'REJECTED_SCREENING'], mandatoryFailed: false, score: 55 }),
    { status: '', reason: 'NONE' },
  );
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'IN_REVIEW', nextStatuses: ['SHORTLIST'], mandatoryFailed: false, score: null }),
    { status: '', reason: 'NONE' },
  );
});

test('không có bước chuyển nào thì không đề xuất gì', () => {
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: 'REJECTED_SCREENING', nextStatuses: [], mandatoryFailed: true, score: 90 }),
    { status: '', reason: 'NONE' },
  );
  assert.deepEqual(
    suggestFinishStatus({ currentStatus: null, nextStatuses: ['SHORTLIST'], mandatoryFailed: false, score: 90 }),
    { status: '', reason: 'NONE' },
  );
});
