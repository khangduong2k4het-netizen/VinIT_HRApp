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
  matchesApplicantOwnership, filterApplicantItemsByOwner, applicantOwnershipCounts, isApplicantOwnership,
} = loadTypeScriptModule('src/lib/applicantOwnership.ts');

const ME = 'user-me';
const items = [
  { application_id: 'a', assigned_to: ME },
  { application_id: 'b', assigned_to: 'user-other' },
  { application_id: 'c', assigned_to: null },
  { application_id: 'd' },
];

test('"Của tôi" chỉ lấy hồ sơ do chính mình giữ', () => {
  assert.deepEqual(
    filterApplicantItemsByOwner(items, 'MINE', ME).map(item => item.application_id),
    ['a'],
  );
});

test('"Chưa ai nhận" gồm cả null lẫn trường vắng mặt', () => {
  assert.deepEqual(
    filterApplicantItemsByOwner(items, 'UNASSIGNED', ME).map(item => item.application_id),
    ['c', 'd'],
  );
});

test('chưa biết người dùng thì "Của tôi" không được coi ai là của mình', () => {
  assert.deepEqual(filterApplicantItemsByOwner(items, 'MINE', null), []);
  assert.equal(matchesApplicantOwnership({ assigned_to: undefined }, 'MINE', ''), false);
});

test('số trên chip tính trên toàn bộ danh sách, không theo bộ lọc đang chọn', () => {
  assert.deepEqual(applicantOwnershipCounts(items, ME), { ALL: 4, MINE: 1, UNASSIGNED: 2 });
  assert.deepEqual(applicantOwnershipCounts([], ME), { ALL: 0, MINE: 0, UNASSIGNED: 0 });
});

test('mã lọc lạ không được nhận để URL không đổi nghĩa', () => {
  assert.equal(isApplicantOwnership('MINE'), true);
  assert.equal(isApplicantOwnership('ALL'), true);
  assert.equal(isApplicantOwnership('OTHERS'), false);
  assert.equal(isApplicantOwnership(null), false);
});
