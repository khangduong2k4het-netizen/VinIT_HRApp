const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  // Module TS thuần có import tương đối (./applicantReview) nên require cần
  // được thay bằng bản dịch TS tại chỗ, đệ quy cho các import tương đối.
  const load = (relative) => {
    const filename = path.join(__dirname, '..', relative);
    const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
      fileName: filename,
    }).outputText;
    const loaded = { exports: {} };
    const localRequire = (request) => {
      if (!request.startsWith('.')) return require(request);
      const resolved = path.relative(path.join(__dirname, '..'), path.resolve(path.dirname(filename), request));
      return load(resolved.endsWith('.ts') ? resolved : `${resolved}.ts`);
    };
    new Function('module', 'exports', 'require', output)(loaded, loaded.exports, localRequire);
    return loaded.exports;
  };
  return load(relativePath);
}

const { buildCriterionRows, countCriterionProgress, criterionRowState } = loadTypeScriptModule('src/lib/criterionQueue.ts');
const { inScreening } = loadTypeScriptModule('src/lib/applicantReview.ts');

const ranking = [
  {
    application_id: 'app-0', candidate_name: 'An', rank_number: 1, application_status: 'IN_REVIEW',
    matching_score: 88, evidence_coverage: 0.9,
    criterion_results: [
      { criterion_id: 'c1', outcome: 'MATCH', score: 70, requires_verification: false },
      { criterion_id: 'c2', outcome: 'UNCLEAR', score: null, requires_verification: true },
    ],
  },
  {
    application_id: 'app-1', candidate_name: 'Bảo', rank_number: 2, application_status: 'SHORTLIST',
    matching_score: 61, evidence_coverage: 0.5,
    criterion_results: [
      { criterion_id: 'c1', outcome: 'NO_MATCH', score: 0, requires_verification: false },
    ],
  },
  {
    application_id: 'app-2', candidate_name: 'Chi', rank_number: 3, application_status: 'REJECTED',
    matching_score: 40, evidence_coverage: 0.4,
    criterion_results: [
      { criterion_id: 'c2', outcome: 'UNCLEAR', score: null, requires_verification: true },
    ],
  },
];

test('danh sách chỉ gồm hồ sơ đang trong xét tuyển và có kết quả cho tiêu chí', () => {
  assert.equal(inScreening('NEW'), true, 'giả định của test: NEW còn trong xét tuyển');
  const rows = buildCriterionRows(ranking, 'c2');
  assert.deepEqual(rows.map(row => row.applicationId), ['app-0'], 'app-1 không có kết quả c2, app-2 đã bị loại');
  assert.equal(rows[0].requiresVerification, true);
  assert.equal(rows[0].outcome, 'UNCLEAR');
});

test('giữ thứ tự xếp hạng và cờ xác minh của từng hồ sơ', () => {
  const rows = buildCriterionRows(ranking, 'c1');
  assert.deepEqual(rows.map(row => [row.applicationId, row.rankNumber, row.requiresVerification]), [
    ['app-0', 1, false],
    ['app-1', 2, false],
  ]);
});

test('chỉ tiêu chí đang chờ mới cho thao tác', () => {
  const base = { loaded: true, hasResultId: true, reviewedDecision: null, canReview: true };
  assert.equal(criterionRowState({ ...base, requiresVerification: true }), 'PENDING');
  assert.equal(criterionRowState({ ...base, requiresVerification: false }), 'NOT_REQUIRED');
  assert.equal(criterionRowState({ ...base, loaded: false }), 'LOADING');
  assert.equal(criterionRowState({ ...base, requiresVerification: true, hasResultId: false }), 'NO_RESULT');
  assert.equal(criterionRowState({ ...base, requiresVerification: true, reviewedDecision: 'CONFIRMED' }), 'REVIEWED');
  assert.equal(criterionRowState({ ...base, requiresVerification: true, reviewedDecision: 'REJECTED' }), 'REVIEWED');
  assert.equal(criterionRowState({ ...base, requiresVerification: true, canReview: false }), 'NO_PERMISSION');
});

test('tiến độ đếm trên hồ sơ bị gắn cờ, không phải mọi dòng', () => {
  const rows = buildCriterionRows(ranking, 'c2');
  const states = { 'app-0': 'PENDING' };
  assert.deepEqual(countCriterionProgress(rows, row => states[row.applicationId] || 'NOT_REQUIRED'), { flagged: 1, verified: 0 });
  assert.deepEqual(countCriterionProgress(rows, () => 'REVIEWED'), { flagged: 1, verified: 1 });
});
