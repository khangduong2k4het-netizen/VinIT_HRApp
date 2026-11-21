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
  // Tin này không liên quan gì tới IT, nhưng chứa "it" giữa chữ "Digital".
  // Có nó thì bug "khớp chuỗi con giữa chữ" mới lộ ra khi chạy test.
  { title: 'Digital Marketing', org_unit: 'Marketing', work_location: 'Hà Nội' },
];

test('từ khoá rỗng trả về nguyên danh sách', () => {
  assert.equal(filterJobs(JOBS, '').length, JOBS.length);
  assert.equal(filterJobs(JOBS, '   ').length, JOBS.length);
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

test('không khớp chuỗi con giữa chữ', () => {
  // Bug thật đã sửa: tìm "IT" bằng includes() khớp cả "Digital" (và "with",
  // "recruit"...). Một từ khoá hai chữ cái lọc ra gần như mọi tin, trông như bộ
  // lọc hỏng. Giờ phải khớp theo ranh giới từ.
  const hit = filterJobs(JOBS, 'IT').map(j => j.title);
  assert.deepEqual(hit, ['BACKEND PYTHON ENGINEER', 'Thực tập sinh Data']);
  assert.ok(!hit.includes('Digital Marketing'), '"IT" không được khớp giữa chữ "Digital"');
});

test('vẫn khớp được tiền tố của một từ', () => {
  // Gõ dở dang là chuyện thường khi đang gõ; chặn hết thì bộ lọc thành vô dụng.
  assert.equal(filterJobs(JOBS, 'back').length, 1);
  assert.equal(filterJobs(JOBS, 'market').length, 1);
});

test('khớp dấu câu bao quanh từ', () => {
  const jobs = [{ title: 'Kỹ sư (backend), 3 năm', org_unit: null, work_location: null }];
  assert.equal(filterJobs(jobs, 'backend').length, 1);
});
