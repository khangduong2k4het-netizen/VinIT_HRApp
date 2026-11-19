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

const review = loadTypeScriptModule('src/lib/applicantReview.ts');
const intake = loadTypeScriptModule('src/lib/intake.ts');

const items = [
  { application_id: 'a', candidate_name: 'A', rank_number: 2, matching_status: 'MEETS_MANDATORY', matching_score: 90, evidence_coverage: 0.9, needs_verification: false, has_mismatch: false, application_status: 'IN_REVIEW', file_processing_status: 'COMPLETED' },
  { application_id: 'b', candidate_name: 'B', rank_number: 1, matching_status: 'MEETS_MANDATORY', matching_score: 80, evidence_coverage: 0.5, needs_verification: true, has_mismatch: false, application_status: 'IN_REVIEW', file_processing_status: 'COMPLETED' },
  { application_id: 'c', candidate_name: 'C', rank_number: null, matching_status: 'NOT_ASSESSED', matching_score: null, evidence_coverage: null, needs_verification: false, has_mismatch: false, application_status: 'NEW', file_processing_status: 'NEEDS_HR_REVIEW', has_duplicate_warning: true },
];

test('applicant queues separate file review, duplicate and verification work', () => {
  const counts = review.applicantQueueCounts(items);
  assert.equal(counts.ALL, 3);
  assert.equal(counts.FILE_REVIEW, 1);
  assert.equal(counts.DUPLICATE, 1);
  assert.equal(counts.NEEDS_VERIFICATION, 1);
  assert.equal(counts.MEETS_MANDATORY, 1);
  assert.deepEqual(review.filterAndSortApplicantItems(items, 'NEEDS_VERIFICATION', '', 'REVIEW_PRIORITY').map(item => item.application_id), ['b']);
});

test('review priority puts file problems before ranking order', () => {
  assert.deepEqual(review.sortApplicantItems(items, 'REVIEW_PRIORITY').map(item => item.application_id), ['c', 'b', 'a']);
  assert.deepEqual(review.sortApplicantItems(items, 'COVERAGE_ASC').map(item => item.application_id), ['b', 'a', 'c']);
});

test('intake validation marks duplicates as warnings and invalid files as blockers', () => {
  const result = intake.validateIntakeFiles([
    { name: 'cv.pdf', size: 100 },
    { name: 'CV.PDF', size: 120 },
    { name: 'notes.txt', size: 100 },
    { name: 'large.pdf', size: 10_000_001 },
  ]);
  assert.equal(result.items[0].status, 'WARNING');
  assert.equal(result.items[1].status, 'WARNING');
  assert.equal(result.items[2].status, 'INVALID');
  assert.equal(result.items[3].status, 'INVALID');
  assert.match(result.batchError, /chưa hợp lệ/);
});


test('route priority can be moved without changing or duplicating the original list', () => {
  const { moveRoute } = loadTypeScriptModule('src/lib/orderedRoutes.ts');
  const routes = ['first', 'second', 'third'];
  assert.deepEqual(moveRoute(routes, 1, -1), ['second', 'first', 'third']);
  assert.deepEqual(moveRoute(routes, 1, 1), ['first', 'third', 'second']);
  assert.deepEqual(routes, ['first', 'second', 'third']);
  assert.deepEqual(moveRoute(routes, 0, -1), routes);
  assert.deepEqual(moveRoute(routes, 2, 1), routes);
  assert.deepEqual(moveRoute(routes, -1, 1), routes);
});


test('LLM cost display distinguishes unknown, free and very small estimates', () => {
  const { formatUsd } = loadTypeScriptModule('src/lib/llmCost.ts');
  assert.equal(formatUsd(null), '—');
  assert.equal(formatUsd(0), '$0');
  assert.equal(formatUsd('0.000000000001'), '$0.000000000001');
  assert.equal(formatUsd('0.450000000000'), '$0.45');
  assert.equal(formatUsd('invalid'), '—');
});

test('scorecard completion requires a recommendation and one valid decision per criterion', () => {
  const { scorecardIsComplete } = loadTypeScriptModule('src/lib/phase2Workflow.ts');
  assert.equal(scorecardIsComplete('RECOMMEND', []), false);
  assert.equal(scorecardIsComplete(null, [{ rating: 5, insufficient_evidence: false }]), false);
  assert.equal(scorecardIsComplete('CONSIDER', [{ rating: null, insufficient_evidence: false }]), false);
  assert.equal(scorecardIsComplete('RECOMMEND', [{ rating: 5, insufficient_evidence: true }]), false);
  assert.equal(scorecardIsComplete('RECOMMEND', [{ rating: 6, insufficient_evidence: false }]), false);
  assert.equal(scorecardIsComplete('CONSIDER', [{ rating: 1, insufficient_evidence: false }, { rating: null, insufficient_evidence: true }]), true);
});

test('rubric form preserves structured requirements and separates keyword input', () => {
  const { rubricKeywords, optionalRequirementSpec } = loadTypeScriptModule('src/lib/phase2Workflow.ts');
  assert.deepEqual(rubricKeywords('Python,  SQL, , TypeScript'), ['Python', 'SQL', 'TypeScript']);
  assert.equal(optionalRequirementSpec('  '), null);
  assert.deepEqual(optionalRequirementSpec('{"kind":"YEARS","min_years":4}'), { kind: 'YEARS', min_years: 4 });
  assert.throws(() => optionalRequirementSpec('{bad'));
});

test('ranking sort follows real rank with unranked last, distinct from review priority', () => {
  assert.deepEqual(review.sortApplicantItems(items, 'RANK').map(item => item.application_id), ['b', 'a', 'c']);
  assert.deepEqual(review.sortApplicantItems(items, 'REVIEW_PRIORITY').map(item => item.application_id), ['c', 'b', 'a']);
  assert.equal(items[0].rank_number, 2); // sorting does not rewrite the actual rank
});


test('large applicant lists mount a bounded window without changing order or ranks', () => {
  const many = Array.from({ length: 123 }, (_, index) => ({ ...items[0], application_id: `id-${index}`, rank_number: index + 1 }));
  const first = review.windowApplicantItems(many, 50);
  assert.equal(first.visible.length, 50);
  assert.equal(first.total, 123);
  assert.equal(first.hasMore, true);
  assert.equal(first.visible[0].application_id, 'id-0');
  assert.equal(first.visible[49].rank_number, 50);
  const expanded = review.windowApplicantItems(many, first.nextLimit);
  assert.equal(expanded.visible.length, 100);
  assert.equal(expanded.hasMore, true);
  const all = review.windowApplicantItems(many, expanded.nextLimit);
  assert.equal(all.visible.length, 123);
  assert.equal(all.hasMore, false);
  // A limit between steps is rounded up so the window never shrinks unexpectedly.
  assert.equal(review.windowApplicantItems(many, 30).visible.length, 50);
});


test('shortlist filter contains only currently shortlisted applications', () => {
  const shortlist = [{ ...items[0], application_status: 'SHORTLIST' }, items[1], items[2]];
  assert.equal(review.applicantQueueCounts(shortlist).SHORTLIST, 1);
  assert.deepEqual(review.filterAndSortApplicantItems(shortlist, 'SHORTLIST', '', 'RANK').map(item => item.application_id), ['a']);
});


test('queue codes from work-queue deep links are accepted in either casing', () => {
  // The backend used to emit ?queue=file_review; the ranking page only knew
  // FILE_REVIEW, so every "review the files" link opened an unfiltered list.
  assert.equal(review.normalizeApplicantQueue('file_review'), 'FILE_REVIEW');
  assert.equal(review.normalizeApplicantQueue('FILE_REVIEW'), 'FILE_REVIEW');
  assert.equal(review.normalizeApplicantQueue('needs_verification'), 'NEEDS_VERIFICATION');
  assert.equal(review.normalizeApplicantQueue('duplicate'), 'DUPLICATE');
  assert.equal(review.normalizeApplicantQueue('possible_mismatch'), 'POSSIBLE_MISMATCH');
  assert.equal(review.normalizeApplicantQueue('not_assessed'), 'NOT_ASSESSED');
  assert.equal(review.normalizeApplicantQueue('meets_mandatory'), 'MEETS_MANDATORY');
  assert.equal(review.normalizeApplicantQueue('shortlist'), 'SHORTLIST');
  assert.equal(review.isApplicantQueue('file_review'), true);
  // Unknown or empty values must not silently become "ALL" behind the reviewer's back.
  assert.equal(review.normalizeApplicantQueue('nonsense'), null);
  assert.equal(review.normalizeApplicantQueue(''), null);
  assert.equal(review.normalizeApplicantQueue(null), null);
  assert.equal(review.isApplicantQueue('nonsense'), false);
});

test('profile links carry the browse context and the list link can restore scroll', () => {
  const profile = review.applicantProfileHref('p1', 'a1', 'NEEDS_VERIFICATION', 'REVIEW_PRIORITY', 'nguyen');
  assert.equal(profile, '/positions/p1/applicants/a1?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY&q=nguyen');
  // Defaults are omitted so links stay readable and comparable.
  assert.equal(review.applicantProfileHref('p1', 'a1', 'ALL', 'RANK', ''), '/positions/p1/applicants/a1');
  assert.equal(review.applicantListHref('p1', 'ALL', 'RANK', ''), '/positions/p1/applicants');
  const list = review.applicantListHref('p1', 'FILE_REVIEW', 'RANK', '');
  assert.equal(list, '/positions/p1/applicants?queue=FILE_REVIEW&sort=RANK');
  // A profile link must be able to rebuild the same list URL it came from.
  const back = new URLSearchParams(profile.split('?')[1]);
  assert.equal(review.readApplicantSearchParams(back.toString()).queue, 'NEEDS_VERIFICATION');
  assert.equal(review.readApplicantSearchParams(back.toString()).search, 'nguyen');
});

test('stored navigation context keeps the scroll offset and normalises old queue codes', () => {
  const store = new Map();
  const original = global.window;
  global.window = {
    sessionStorage: {
      getItem: key => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, value),
    },
  };
  try {
    review.storeApplicantNavigation({
      positionId: 'p1', queue: 'FILE_REVIEW', sort: 'REVIEW_PRIORITY', search: 'an',
      applicationIds: ['a1'], storedAt: 1, scrollY: 640,
    });
    const stored = review.readApplicantNavigation('p1');
    assert.equal(stored.scrollY, 640);
    assert.equal(stored.queue, 'FILE_REVIEW');

    // A context written before the casing fix still filters correctly.
    store.set('hra-applicant-navigation:p1', JSON.stringify({
      positionId: 'p1', queue: 'needs_verification', sort: 'RANK', search: '',
      applicationIds: [], storedAt: 1,
    }));
    assert.equal(review.readApplicantNavigation('p1').queue, 'NEEDS_VERIFICATION');
  } finally {
    global.window = original;
  }
});

test('applicant queue labels stay in one place for chips and summaries', () => {
  // The chips and the "Queue: ..." summary must never drift apart.
  assert.equal(review.APPLICANT_QUEUE_LABELS.FILE_REVIEW, 'Cần kiểm tra file');
  assert.equal(review.APPLICANT_QUEUE_LABELS.NEEDS_VERIFICATION, 'Cần xác minh');
  assert.equal(Object.keys(review.APPLICANT_QUEUE_LABELS).length, review.APPLICANT_QUEUES.length);
});
