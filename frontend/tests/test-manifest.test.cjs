// Test này canh chính việc test: mọi file *.test.cjs phải được khai trong
// package.json, nếu không nó sẽ không bao giờ chạy trên CI.
//
// Lý do tồn tại: 3 file test của đợt lịch phỏng vấn (37 test) đã nằm trong
// repo nhưng KHÔNG có trong test:unit. Chúng xanh trên máy người viết và
// không chạy ở đâu cả. Cùng loại lỗi với CI đỏ 11 ngày: tin vào thứ chưa
// thực sự chạy.
const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');

function declaredTestFiles() {
  const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  const found = new Set();
  for (const script of Object.values(pkg.scripts || {})) {
    for (const token of String(script).split(/\s+/)) {
      if (token.includes('tests/') && token.endsWith('.cjs')) {
        found.add(token.replace(/^node\s+/, '').replace(/^tests\//, ''));
      }
    }
  }
  return found;
}

test('moi file test deu duoc khai trong package.json', () => {
  const declared = declaredTestFiles();
  const onDisk = fs.readdirSync(path.join(ROOT, 'tests'))
    .filter((name) => name.endsWith('.test.cjs'));
  const missing = onDisk.filter((name) => !declared.has(name));
  assert.deepStrictEqual(
    missing, [],
    'File test chưa được khai trong scripts của package.json nên không chạy trên CI: '
      + missing.join(', '),
  );
});

test('khong khai file test khong ton tai', () => {
  const declared = declaredTestFiles();
  const onDisk = new Set(fs.readdirSync(path.join(ROOT, 'tests')));
  const ghosts = [...declared].filter((name) => !onDisk.has(name));
  assert.deepStrictEqual(ghosts, [], 'Khai file test không có thật: ' + ghosts.join(', '));
});
