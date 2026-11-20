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

const {
  readRecentReasons, rememberReason, normalizeReason, rejectionReasonsKey,
  criterionReasonCandidates, REJECTION_REASONS_MAX,
} = loadTypeScriptModule('src/lib/rejectionReasons.ts');

function fakeStorage(initial) {
  const data = new Map(initial ? [[rejectionReasonsKey('p1'), initial]] : []);
  return {
    data,
    getItem: key => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => { data.set(key, value); },
  };
}

const POSITION = 'p1';

test('lý do đã dùng được nhớ theo vị trí, mới nhất trước và không trùng', () => {
  const storage = fakeStorage();
  rememberReason(POSITION, 'Không đáp ứng: thiếu chứng chỉ', storage);
  rememberReason(POSITION, 'Không đủ kinh nghiệm backend', storage);
  rememberReason(POSITION, '  không đủ   KINH NGHIỆM backend ', storage);

  assert.deepEqual(readRecentReasons(POSITION, storage), [
    'không đủ KINH NGHIỆM backend',
    'Không đáp ứng: thiếu chứng chỉ',
  ], 'khoảng trắng và hoa/thường không tạo ra hai lý do khác nhau');
});

test('số lý do nhớ được có trần, giữ cái mới nhất', () => {
  const storage = fakeStorage();
  for (let i = 0; i < REJECTION_REASONS_MAX + 5; i += 1) {
    rememberReason(POSITION, `Lý do ${i}`, storage);
  }
  const reasons = readRecentReasons(POSITION, storage);
  assert.equal(reasons.length, REJECTION_REASONS_MAX);
  assert.equal(reasons[0], `Lý do ${REJECTION_REASONS_MAX + 4}`);
});

test('lý do thuộc đúng vị trí: vị trí khác không thấy gợi ý của nhau', () => {
  const storage = fakeStorage();
  rememberReason('p1', 'thiếu kinh nghiệm', storage);
  assert.deepEqual(readRecentReasons('p2', storage), []);
});

test('storage hỏng hoặc bị chặn không làm hỏng thao tác', () => {
  assert.deepEqual(readRecentReasons(POSITION, fakeStorage('{not json')), []);
  assert.deepEqual(readRecentReasons(POSITION, fakeStorage('{"a":1}')), []);
  assert.deepEqual(readRecentReasons(POSITION, fakeStorage('["ok", 3, null]')), ['ok']);
  const throwing = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.deepEqual(readRecentReasons(POSITION, throwing), []);
  assert.doesNotThrow(() => rememberReason(POSITION, 'lý do', throwing));
  assert.equal(normalizeReason('  nhiều   dấu cách\nxuống dòng '), 'nhiều dấu cách xuống dòng');
});

const criterion = (id, name, category = 'MUST_HAVE', spec = null) => ({
  criterion_id: id,
  criteria_version_id: 'v1',
  name,
  description: '',
  category,
  weight_in_group: 10,
  expected_evidence_keywords: [],
  requirement_spec: spec,
  display_order: 0,
});

const result = (criterionId, name, outcome, category = 'MUST_HAVE') => ({
  criterion_id: criterionId,
  criterion_name: name,
  category,
  outcome,
  score: null,
  confidence: null,
  reasoning: null,
  requires_verification: true,
});

test('gợi ý chỉ đến từ tiêu chí bắt buộc chưa đạt hoặc chưa rõ', () => {
  const criteria = [
    criterion('years', 'Kinh nghiệm Python', 'MUST_HAVE', { kind: 'YEARS', terms: ['Python'], min_years: 3, required_languages: [] }),
    criterion('nice', 'Docker', 'NICE_TO_HAVE', { kind: 'SKILL', terms: ['Docker'], required_languages: [] }),
    criterion('degree', 'Bằng đại học', 'MUST_HAVE', { kind: 'DEGREE', terms: [], required_degree_level: 5, required_languages: [] }),
  ];
  const candidates = criterionReasonCandidates(criteria, [
    result('years', 'Kinh nghiệm Python', 'NO_MATCH'),
    result('nice', 'Docker', 'NO_MATCH', 'NICE_TO_HAVE'),
    result('degree', 'Bằng đại học', 'UNCLEAR'),
    result('years', 'Kinh nghiệm Python', 'MATCH'),
  ]);

  assert.equal(candidates.length, 2, 'ưu tiên không phải lý do loại; kết quả MATCH không lặp lại');
  assert.equal(candidates[0].criterion_id, 'years');
  assert.equal(candidates[0].outcome, 'NO_MATCH');
  assert.equal(candidates[0].spec.min_years, 3, 'giữ spec để UI nói "≥ 3 năm Python"');
  assert.equal(candidates[1].outcome, 'UNCLEAR');
  assert.equal(candidates[1].spec.required_degree_level, 5);
});

test('gợi ý dùng tên tiêu chí khi thiếu đặc tả, và có trần số gợi ý', () => {
  const criteria = [criterion('a', 'Giao tiếp tiếng Anh')];
  const candidates = criterionReasonCandidates(criteria, [result('a', 'Giao tiếp tiếng Anh', 'NO_MATCH')]);
  assert.equal(candidates[0].name, 'Giao tiếp tiếng Anh');
  assert.equal(candidates[0].spec, null);

  const many = ['a', 'b', 'c', 'd'].map(id => result(id, `Tiêu chí ${id}`, 'NO_MATCH'));
  assert.equal(criterionReasonCandidates([], many, 3).length, 3);
  // Không có tên nào để nói thì không sinh gợi ý rỗng.
  assert.deepEqual(criterionReasonCandidates([], [result('x', '  ', 'NO_MATCH')]), []);
});
