const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8');
const en = require('../src/i18n/en.json');

test('login help separates users (ask an Admin) from Admins (recovery key)', () => {
  const page = read('src/app/login-help/page.tsx');
  assert.match(page, /router\.push\('\/forgot-password'\)/);
  assert.match(page, /router\.push\('\/admin-recovery'\)/);
  assert.match(page, /admin_recovery/);
  for (const key of ['Trợ giúp đăng nhập', 'Tôi là HR / người dùng và quên mật khẩu', 'Tôi là Admin và không đăng nhập được', 'Cần trợ giúp đăng nhập?']) {
    assert.ok(en[key], key);
  }
});

test('admin recovery asks for the key first, lists Admins, and uses the eye password fields', () => {
  const page = read('src/app/admin-recovery/page.tsx');
  assert.match(page, /recoveryAdmins\(/);
  assert.match(page, /recoveryReset\(/);
  assert.match(page, /PasswordField/);
  assert.ok(!/localStorage/.test(page), 'the key is never stored');
});

test('both pages are public routes and the Admin screen warns about a single Admin', () => {
  const layout = read('src/components/layout/AppLayout.tsx');
  assert.match(layout, /'\/login-help'/);
  assert.match(layout, /'\/admin-recovery'/);
  assert.match(read('src/app/admin/users/page.tsx'), /activeAdmins <= 1/);
});

test('a wrong recovery key shows an error on the page instead of bouncing to the login page', () => {
  assert.match(read('src/lib/api.ts'), /!error\.config\?\.url\?\.includes\('\/auth\/recovery'\)/);
});

test('admin recovery offers two clear ways: the key (no email) and a confirmation mail', () => {
  const page = read('src/app/admin-recovery/page.tsx');
  assert.match(page, /recoveryEmail\(/);
  assert.match(page, /setMode\('key'\)/);
  assert.match(page, /setMode\('email'\)/);
  for (const key of ['Tôi có mã khôi phục', 'Tôi chưa có mã / làm mất mã', 'Gửi thư xác nhận']) assert.ok(en[key], key);
});
