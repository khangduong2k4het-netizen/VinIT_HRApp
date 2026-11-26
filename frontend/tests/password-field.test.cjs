const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8');
const field = read('src/components/common/PasswordField.tsx');
const en = require('../src/i18n/en.json');

test('password field is hidden by default, toggles with a labelled button and hides again on submit', () => {
  assert.match(field, /useState\(false\)/);
  assert.match(field, /type=\{show \? 'text' : 'password'\}/);
  assert.match(field, /aria-label=\{label\}/);
  assert.match(field, /addEventListener\('submit'/);
  assert.equal(en['Hiện mật khẩu'], 'Show password');
  assert.equal(en['Ẩn mật khẩu'], 'Hide password');
});

test('every real password input uses the shared field (only API key / setup token stay plain)', () => {
  for (const rel of ['src/app/page.tsx', 'src/app/change-password/page.tsx', 'src/app/reset-password/page.tsx', 'src/app/register/page.tsx',
    'src/app/bootstrap/page.tsx', 'src/app/admin/users/page.tsx']) {
    const text = read(rel);
    assert.match(text, /PasswordField/, rel);
    const plain = text.split('\n').filter(line => /type="password"/.test(line) && !/Mã khởi tạo|API Key/.test(line));
    assert.deepEqual(plain, [], rel);
  }
});
