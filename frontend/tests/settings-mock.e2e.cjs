const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use a local disposable Next.js server.');
}
const json = (r, body, status = 200) => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

const SETTINGS = [
  { key: 'deadline_soon_days', value: 7, default: 7, min: 1, max: 60, label: 'Số ngày báo trước khi hết hạn ứng tuyển', description: 'Vị trí còn ít hơn hoặc bằng số ngày này sẽ hiện việc "Vị trí sắp hết hạn ứng tuyển" trên Dashboard.' },
  { key: 'waiting_attention_days', value: 7, default: 7, min: 1, max: 90, label: 'Số ngày hồ sơ được tính là chờ lâu', description: 'Hồ sơ đang sàng lọc lâu hơn số ngày này được đếm vào dòng "hồ sơ chờ quá N ngày" trên Dashboard.' },
];

// HR settings: a number that is out of range must be refused *before* a round
// trip, and a valid one must be sent with the value HR typed.
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const c = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await c.addInitScript(() => { localStorage.setItem('hra_access_token', 'test'); localStorage.setItem('hra_locale', 'vi'); });

  const patches = [];
  await c.route('**/v1/**', async r => {
    const url = new URL(r.request().url());
    const p = url.pathname;
    const method = r.request().method();
    if (p === '/v1/auth/me') return json(r, { user_id: 'admin', display_name: 'Admin', system_roles: ['ADMIN'], position_assignments: [] });
    if (p === '/v1/admin/settings' && method === 'GET') return json(r, { settings: SETTINGS });
    if (p === '/v1/admin/settings/deadline_soon_days' && method === 'PATCH') {
      patches.push(r.request().postDataJSON());
      return json(r, { key: 'deadline_soon_days', value: r.request().postDataJSON().value, previous_value: 7 });
    }
    if (p.startsWith('/v1/admin/')) return json(r, {});
    return json(r, {});
  });

  const page = await c.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`${base}/admin/settings`, { waitUntil: 'networkidle' });
  await page.getByTestId('hr-settings').waitFor();

  const fields = page.locator('[data-testid="hr-settings"] input[type="number"]');
  assert.equal(await fields.count(), 2, 'both thresholds are editable');
  const saveButtons = page.locator('[data-testid="hr-settings"] button', { hasText: 'Lưu' });
  assert.equal(await saveButtons.nth(0).isDisabled(), true, 'saving is disabled until something changes');

  // Out of range: no request must leave the browser.
  await fields.nth(0).fill('61');
  assert.equal(await saveButtons.nth(0).isDisabled(), true, 'an out-of-range value cannot be submitted');
  assert.match(await page.locator('[data-testid="hr-settings"]').innerText(), /Ngoài khoảng cho phép/);

  // Valid change: exactly one request, with the typed value.
  await fields.nth(0).fill('5');
  assert.equal(await saveButtons.nth(0).isDisabled(), false);
  await saveButtons.nth(0).click();
  await page.waitForFunction(() => document.body.innerText.includes('Đã lưu'));
  assert.deepEqual(patches, [{ value: 5 }], 'the typed number is what gets saved');

  // "Did it save?" must never be a guess: the row itself confirms, next to the
  // button the person just pressed, and screen readers are told politely.
  const row = page.locator('[data-testid="hr-settings"] > *').first();
  assert.match(await row.innerText(), /Đã lưu lúc \d{1,2}:\d{2}/, 'the saved row confirms in place');
  const status = row.locator('[role="status"]');
  assert.equal(await status.getAttribute('aria-live'), 'polite');
  assert.match(await status.innerText(), /Đã lưu lúc/);

  // Editing again clears the stale confirmation so it cannot describe the old value.
  await fields.nth(0).fill('6');
  assert.equal(await row.innerText().then(t => /Đã lưu lúc/.test(t)), false, 'a pending edit drops the old confirmation');

  // A server-side rejection must be shown, not swallowed.
  await c.unroute('**/v1/**');
  await c.route('**/v1/**', async r => {
    const url = new URL(r.request().url());
    const p = url.pathname;
    if (p === '/v1/auth/me') return json(r, { user_id: 'admin', display_name: 'Admin', system_roles: ['ADMIN'], position_assignments: [] });
    if (p === '/v1/admin/settings' && r.request().method() === 'GET') return json(r, { settings: SETTINGS.map(s => ({ ...s, value: 5 })) });
    if (p === '/v1/admin/settings/waiting_attention_days' && r.request().method() === 'PATCH') return json(r, { detail: '"Số ngày hồ sơ được tính là chờ lâu" phải nằm trong khoảng 1–90 ngày' }, 400);
    if (p.startsWith('/v1/admin/')) return json(r, {});
    return json(r, {});
  });
  await fields.nth(1).fill('4');
  await saveButtons.nth(1).click();
  await page.getByRole('alert').filter({ hasText: 'phải nằm trong khoảng 1–90 ngày' }).waitFor();
  assert.equal(await page.locator('[data-testid="hr-settings"]').innerText().then(t => /Đã lưu lúc/.test(t)), false, 'a failed save must not leave a success mark');

  if (errors.length) throw Error(errors.join('\n'));
  await c.close();
  await browser.close();
  console.log('HR settings: range enforced before saving, change saved with the typed value: OK; all /v1 intercepted');
})().catch(e => { console.error(e); process.exit(1); });
