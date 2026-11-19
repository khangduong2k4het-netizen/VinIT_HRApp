const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

// Nạp module TS vào bộ nhớ; `shims` thay một import bằng giá trị thật.
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

const vocabulary = loadTypeScriptModule('src/lib/workVocabulary.ts');
const review = loadTypeScriptModule('src/lib/applicantReview.ts', { './workVocabulary': vocabulary });
const { DEFAULT_APPLICANT_CRITERIA_FILTER, filterAndSortApplicantItems, matchesApplicantCriteriaFilter, hasApplicantCriteriaFilter } = review;

const NOW = new Date('2026-11-19T00:00:00Z');
const daysAgo = days => new Date(NOW.getTime() - days * 86_400_000).toISOString();

const criterion = (criterionId, outcome, requiresVerification = false) => ({
  criterion_id: criterionId,
  criterion_name: `Tiêu chí ${criterionId}`,
  category: 'MUST_HAVE',
  outcome,
  score: outcome === 'MATCH' ? 80 : 40,
  effective_weight: 30,
  requires_verification: requiresVerification,
});

const item = (applicationId, overrides = {}) => ({
  application_id: applicationId,
  candidate_name: `Ứng viên ${applicationId}`,
  rank_number: 1,
  matching_status: 'MEETS_MANDATORY',
  matching_score: 80,
  evidence_coverage: 0.9,
  needs_verification: false,
  has_mismatch: false,
  application_status: 'IN_REVIEW',
  created_at: daysAgo(1),
  criterion_results: [],
  ...overrides,
});

const ids = rows => rows.map(row => row.application_id);

test('the old four-argument call still returns the whole queue', () => {
  // Backward compatibility: screens that do not know about the evidence filter.
  const items = [item('a'), item('b')];
  assert.deepEqual(ids(filterAndSortApplicantItems(items, 'ALL', '', 'RANK')), ['a', 'b']);
  assert.equal(hasApplicantCriteriaFilter(DEFAULT_APPLICANT_CRITERIA_FILTER), false);
});

test('"missing evidence for criterion X" includes unclear, unverified and never-assessed rows', () => {
  const filter = { criterionId: 'c1', outcome: 'MISSING', verificationWaitingDays: null };
  const items = [
    item('unclear', { criterion_results: [criterion('c1', 'UNCLEAR')] }),
    item('unverified', { criterion_results: [criterion('c1', 'MATCH', true)] }),
    item('absent', { criterion_results: [criterion('c2', 'MATCH')] }),
    item('not-assessed', { matching_status: 'NOT_ASSESSED', criterion_results: [] }),
    item('met', { criterion_results: [criterion('c1', 'MATCH')] }),
    item('failed', { criterion_results: [criterion('c1', 'NO_MATCH')] }),
  ];
  assert.deepEqual(ids(items.filter(row => matchesApplicantCriteriaFilter(row, filter, NOW))), ['unclear', 'unverified', 'absent', 'not-assessed']);
  assert.equal(hasApplicantCriteriaFilter(filter), true);
});

test('an outcome other than missing narrows to that exact result', () => {
  const items = [
    item('met', { criterion_results: [criterion('c1', 'MATCH')] }),
    item('strong', { criterion_results: [criterion('c1', 'STRONG_MATCH')] }),
    item('failed', { criterion_results: [criterion('c1', 'NO_MATCH')] }),
    item('unclear', { criterion_results: [criterion('c1', 'UNCLEAR')] }),
  ];
  const pick = (outcome) => ids(items.filter(row =>
    matchesApplicantCriteriaFilter(row, { criterionId: 'c1', outcome, verificationWaitingDays: null }, NOW),
  ));
  assert.deepEqual(pick('NO_MATCH'), ['failed']);
  assert.deepEqual(pick('UNCLEAR'), ['unclear']);
  assert.deepEqual(pick('MATCH'), ['met', 'strong']);
  assert.deepEqual(pick('ALL'), ['met', 'strong', 'failed', 'unclear']);
});

test('"waiting for my verification over N days" needs both the flag and the age', () => {
  const items = [
    item('old', { needs_verification: true, created_at: daysAgo(10) }),
    item('fresh', { needs_verification: true, created_at: daysAgo(2) }),
    item('unknown-date', { needs_verification: true, created_at: undefined }),
    item('not-waiting', { needs_verification: false, created_at: daysAgo(30) }),
  ];
  const overThree = { criterionId: null, outcome: 'ALL', verificationWaitingDays: 3 };
  assert.deepEqual(ids(items.filter(row => matchesApplicantCriteriaFilter(row, overThree, NOW))), ['old']);
  // "Any application awaiting me" ignores the age, but still requires the flag.
  const anyWaiting = { criterionId: null, outcome: 'ALL', verificationWaitingDays: 0 };
  assert.deepEqual(ids(items.filter(row => matchesApplicantCriteriaFilter(row, anyWaiting, NOW))), ['old', 'fresh', 'unknown-date']);
});

test('queue, evidence and name filters combine instead of overriding each other', () => {
  const items = [
    item('shortlisted', { application_status: 'SHORTLIST', criterion_results: [criterion('c1', 'UNCLEAR')] }),
    item('in-review', { criterion_results: [criterion('c1', 'UNCLEAR')] }),
    item('assessed', { criterion_results: [criterion('c1', 'MATCH')] }),
  ];
  const filter = { criterionId: 'c1', outcome: 'MISSING', verificationWaitingDays: null };
  // Same rank and score in this fixture, so the tie-break is the name.
  assert.deepEqual(ids(filterAndSortApplicantItems(items, 'ALL', '', 'RANK', filter, NOW)), ['in-review', 'shortlisted']);
  assert.deepEqual(ids(filterAndSortApplicantItems(items, 'SHORTLIST', '', 'RANK', filter, NOW)), ['shortlisted']);
  assert.deepEqual(ids(filterAndSortApplicantItems(items, 'ALL', 'in-review', 'RANK', filter, NOW)), ['in-review']);
});
