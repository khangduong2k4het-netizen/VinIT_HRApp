const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../src/app/page.tsx'), 'utf8');

test('login always tells people to ask an Admin, whether or not email reset is available', () => {
  const note = source.indexOf('Liên hệ Admin để đặt lại mật khẩu');
  assert.ok(note > 0);
  // Not inside the conditional that shows the email "Quên mật khẩu?" link.
  const emailBlock = source.slice(source.indexOf('config.password_reset &&'), note);
  assert.ok(!/config\.password_reset\s*\?/.test(source), 'the note must not depend on config.password_reset');
  assert.ok(emailBlock.length > 0 && source.indexOf('© ') > note, 'the note sits above the copyright line');
});

test('login links are centred under the form, not left-aligned', () => {
  assert.match(source, /flexDirection: 'column', alignItems: 'center'/);
  assert.ok(!/justifyContent: 'space-between'[^]*Quên mật khẩu\?/.test(source));
});
