const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');

const read = rel => fs.readFileSync(path.join(__dirname, '..', rel), 'utf8');
const en = require('../src/i18n/en.json');

test('forgot-password page asks for the email and a reason and posts a request for the Admin', () => {
  const page = read('src/app/forgot-password/page.tsx');
  assert.match(page, /requestPasswordReset\(email\.trim\(\), reason\.trim\(\), fullName\.trim\(\), unit\.trim\(\)\)/);
  assert.match(page, /Họ và tên/);
  assert.match(page, /Đơn vị \/ phòng ban/);
  assert.match(page, /maxLength: REASON_MAX/);
  assert.ok(!/dev_reset_link/.test(page));
});

test('Admin account page shows the request queue with approve and reject', () => {
  assert.match(read('src/app/admin/users/page.tsx'), /<ResetRequestsPanel \/>/);
  const panel = read('src/components/admin/ResetRequestsPanel.tsx');
  assert.match(panel, /approveResetRequest/);
  assert.match(panel, /rejectResetRequest/);
  for (const key of ['Duyệt và gửi link', 'Từ chối', 'Yêu cầu đặt lại mật khẩu', 'Gửi yêu cầu cho Admin']) assert.ok(en[key], key);
});

test('Admin queue labels requests that match no account and only offers Handled / Dismiss for them', () => {
  const panel = read('src/components/admin/ResetRequestsPanel.tsx');
  assert.match(panel, /Không khớp tài khoản nào/);
  assert.match(panel, /resolveResetRequest/);
  assert.match(panel, /item\.kind === 'UNMATCHED'/);
  for (const key of ['Không khớp tài khoản nào', 'Đã xử lý', 'Bỏ qua', 'Họ và tên', 'Đơn vị / phòng ban']) assert.ok(en[key], key);
});
