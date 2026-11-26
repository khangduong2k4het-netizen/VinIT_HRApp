const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../src/app/page.tsx'), 'utf8');

test('login is kept simple: one neutral help link, nothing about recovery next to it', () => {
  assert.match(source, /router\.push\('\/login-help'\)/);
  assert.match(source, /Cần trợ giúp đăng nhập\?/);
  assert.ok(!/forgot-password|admin-recovery|Gửi yêu cầu cho Admin|Liên hệ Admin/.test(source));
  assert.ok(!/config\.password_reset/.test(source));
  assert.ok(source.indexOf('© ') > source.indexOf('Cần trợ giúp đăng nhập?'), 'the link sits above the copyright line');
});

test('login links are centred under the form, not left-aligned', () => {
  assert.match(source, /flexDirection: 'column', alignItems: 'center'/);
  assert.ok(!/justifyContent: 'space-between'[^]*Quên mật khẩu\?/.test(source));
});
