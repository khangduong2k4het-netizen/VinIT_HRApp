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

const { notesForCriterion, generalNotes, summarizeCriterionNotes } = loadTypeScriptModule('src/lib/criterionNotes.ts');

const note = (id, criterionId = null) => ({
  note_id: id,
  content: `nội dung ${id}`,
  criterion_id: criterionId,
  created_at: '2026-11-19T08:00:00Z',
  author_name: 'HR A',
});

test('ghi chú theo tiêu chí chỉ hiện ở đúng tiêu chí đó', () => {
  const notes = [note('1', 'c1'), note('2', 'c2'), note('3'), note('4', 'c1')];
  assert.deepEqual(notesForCriterion(notes, 'c1').map(n => n.note_id), ['1', '4']);
  assert.deepEqual(notesForCriterion(notes, 'c2').map(n => n.note_id), ['2']);
  assert.deepEqual(notesForCriterion(notes, 'c9'), []);
  assert.deepEqual(notesForCriterion(notes, ''), [], 'không có tiêu chí thì không gắn bừa');
});

test('bảng ghi chú cuối trang chỉ chứa ghi chú chung', () => {
  const notes = [note('1', 'c1'), note('2'), note('3', null)];
  assert.deepEqual(generalNotes(notes).map(n => n.note_id), ['2', '3']);
});

test('dòng tổng hợp đếm cả ghi chú chung lẫn ghi chú theo tiêu chí', () => {
  assert.deepEqual(summarizeCriterionNotes([note('1', 'c1'), note('2', 'c1'), note('3')]), {
    total: 3,
    criteriaWithNotes: 1,
  });
  assert.deepEqual(summarizeCriterionNotes([]), { total: 0, criteriaWithNotes: 0 });
});
