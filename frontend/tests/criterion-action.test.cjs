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

const { determineCriterionAction } = loadTypeScriptModule('src/lib/criterionAction.ts');

const confirmed = { review_id: 'r1', decision: 'CONFIRMED', reviewer_user_id: 'u1', created_at: '2026-11-19T09:00:00Z' };
const rejected = { review_id: 'r2', decision: 'REJECTED', comment: 'CV không nêu', reviewer_user_id: 'u1', created_at: '2026-11-19T09:00:00Z' };

function criterion(overrides = {}) {
  return {
    outcome: 'MATCH',
    requires_verification: false,
    page_number: 2,
    verbatim_quote: 'Một đoạn trích',
    evidence: [{ evidence_id: 'e1', page_number: 2, verification_status: 'VERIFIED' }],
    hr_reviews: [],
    ...overrides,
  };
}

test('a recorded confirmation ends the work, whatever the engine said', () => {
  // The engine's verdict must not resurrect a task after a person decided.
  const action = determineCriterionAction(criterion({ requires_verification: true, hr_reviews: [confirmed] }));
  assert.equal(action.code, 'CONFIRMED');
  assert.equal(action.weight, 'none');
});

test('a recorded rejection asks for a second look, not a repeat of the same click', () => {
  const action = determineCriterionAction(criterion({ requires_verification: true, hr_reviews: [rejected] }));
  assert.equal(action.code, 'REVIEWED_AS_WRONG');
  assert.equal(action.weight, 'act');
});

test('a failed citation is a manual check, stronger than "not checked yet"', () => {
  // Both used to render as "Trích dẫn chưa xác minh"; the reviewer could not tell
  // "the CV does not contain this" from "nobody looked".
  const failed = determineCriterionAction(criterion({
    evidence: [{ evidence_id: 'e1', page_number: 2, verification_status: 'FAILED' }],
  }));
  assert.equal(failed.code, 'MISMATCH_CHECK');

  const pending = determineCriterionAction(criterion({
    requires_verification: true,
    evidence: [{ evidence_id: 'e1', page_number: 2, verification_status: 'PENDING' }],
  }));
  assert.equal(pending.code, 'NEEDS_CHECK');
});

test('a flagged criterion with no quote is an interview question, not a CV task', () => {
  const action = determineCriterionAction(criterion({
    outcome: 'UNCLEAR',
    requires_verification: true,
    evidence: [],
    verbatim_quote: null,
    page_number: null,
  }));
  assert.equal(action.code, 'NOT_IN_CV');
});

test('a flagged criterion with a page names the page to compare against', () => {
  const action = determineCriterionAction(criterion({ requires_verification: true }));
  assert.equal(action.code, 'NEEDS_CHECK');
  assert.match(action.text, /trang \{0\}/);
});

test('a flagged criterion with no page still asks for a check, without inventing a page', () => {
  const action = determineCriterionAction(criterion({
    requires_verification: true,
    page_number: null,
    evidence: [{ evidence_id: 'e1', page_number: null, verification_status: 'PENDING' }],
  }));
  assert.equal(action.code, 'NEEDS_CHECK');
  assert.doesNotMatch(action.text, /trang/);
});

test('verified and unflagged means genuinely nothing to do', () => {
  assert.equal(determineCriterionAction(criterion()).code, 'ENOUGH_EVIDENCE');
});

test('unverified but unflagged is a look, not a task', () => {
  const action = determineCriterionAction(criterion({
    evidence: [{ evidence_id: 'e1', page_number: 2, verification_status: 'PENDING' }],
  }));
  assert.equal(action.code, 'OPEN_CV');
  assert.equal(action.weight, 'look');
});

test('no evidence and no flag states the uncertainty instead of inventing a task', () => {
  const action = determineCriterionAction(criterion({
    outcome: 'NO_MATCH',
    evidence: [],
    verbatim_quote: null,
    page_number: null,
  }));
  assert.equal(action.code, 'OPEN_CV');
  assert.match(action.text, /Chưa có bằng chứng/);
});

test('every code the function can return is reachable', () => {
  // Guards against a branch that silently became dead code after an edit.
  const seen = new Set([
    determineCriterionAction(criterion({ hr_reviews: [confirmed] })).code,
    determineCriterionAction(criterion({ hr_reviews: [rejected] })).code,
    determineCriterionAction(criterion({ requires_verification: true })).code,
    determineCriterionAction(criterion({ requires_verification: true, evidence: [], verbatim_quote: null })).code,
    determineCriterionAction(criterion({ evidence: [{ evidence_id: 'e', page_number: 2, verification_status: 'FAILED' }] })).code,
    determineCriterionAction(criterion()).code,
    determineCriterionAction(criterion({ evidence: [] })).code,
  ]);
  assert.deepEqual([...seen].sort(), [
    'CONFIRMED', 'ENOUGH_EVIDENCE', 'MISMATCH_CHECK', 'NEEDS_CHECK',
    'NOT_IN_CV', 'OPEN_CV', 'REVIEWED_AS_WRONG',
  ]);
});
