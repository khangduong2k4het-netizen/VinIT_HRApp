const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../src/app/page.tsx'), 'utf8');

test('login links to a request form for the Admin (no email self-service, no loose note)', () => {
  assert.match(source, /router\.push\('\/forgot-password'\)/);
  assert.match(source, /Quên mật khẩu\? Gửi yêu cầu cho Admin/);
  assert.ok(!/Liên hệ Admin để đặt lại mật khẩu/.test(source));
  assert.ok(!/config\.password_reset/.test(source));
  assert.ok(source.indexOf('© ') > source.indexOf('Gửi yêu cầu cho Admin'), 'the link sits above the copyright line');
});

test('login links are centred under the form, not left-aligned', () => {
  assert.match(source, /flexDirection: 'column', alignItems: 'center'/);
  assert.ok(!/justifyContent: 'space-between'[^]*Quên mật khẩu\?/.test(source));
});
