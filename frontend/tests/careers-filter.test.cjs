const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
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

const { filterJobs } = loadTypeScriptModule('src/lib/careersFilter.ts');

const JOBS = [
  { title: 'BACKEND PYTHON ENGINEER', org_unit: 'IT', work_location: 'Hà Nội' },
  { title: 'Thực tập sinh Data', org_unit: 'IT', work_location: 'Đà Nẵng' },
  { title: 'Chuyên viên Nhân sự', org_unit: 'HR', work_location: null },
];

test('từ khoá rỗng trả về nguyên danh sách', () => {
  assert.equal(filterJobs(JOBS, '').length, 3);
  assert.equal(filterJobs(JOBS, '   ').length, 3);
});

test('khớp theo chức danh, không phân biệt hoa thường', () => {
  assert.deepEqual(filterJobs(JOBS, 'backend').map(j => j.org_unit), ['IT']);
  assert.equal(filterJobs(JOBS, 'PYTHON').length, 1);
});

test('khớp cả đơn vị và địa điểm, không chỉ chức danh', () => {
  // Hai vị trí ở IT: gõ "it" phải ra cả hai, không phải chỉ tin có chữ IT trong tên.
  assert.equal(filterJobs(JOBS, 'IT').length, 2);
  assert.equal(filterJobs(JOBS, 'đà nẵng').length, 1);
});

test('trường null không làm vỡ bộ lọc', () => {
  // work_location của "Chuyên viên Nhân sự" là null: gọi .toLowerCase() trên null
  // sẽ ném, và lỗi đó chỉ lộ ra khi có tin thiếu địa điểm — đúng tin hay gặp.
  assert.doesNotThrow(() => filterJobs(JOBS, 'nhân sự'));
  assert.equal(filterJobs(JOBS, 'nhân sự').length, 1);
});

test('không cắt dấu tiếng Việt', () => {
  // Cắt dấu là đoán ý người dùng: "thuc" và "thực" là hai từ khác nhau, và một
  // bộ lọc tự đoán sẽ trả về những tin người dùng không hề tìm.
  assert.equal(filterJobs(JOBS, 'thuc').length, 0);
  assert.equal(filterJobs(JOBS, 'thực').length, 1);
});

test('không khớp gì thì trả mảng rỗng, không ném', () => {
  assert.deepEqual(filterJobs(JOBS, 'không có gì'), []);
});

test('không sửa mảng gốc', () => {
  const copy = JSON.parse(JSON.stringify(JOBS));
  filterJobs(JOBS, 'backend');
  assert.deepEqual(JOBS, copy);
});
