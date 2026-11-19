/**
 * Capture the new HR settings screen for review, at the two sizes that matter:
 * desktop and a 390px phone. Read-only: the mock answers the API, nothing is saved.
 *
 *   HRA_E2E_BASE_URL=http://localhost:3015 \
 *   HRA_E2E_CHROMIUM_EXECUTABLE=/tmp/chromium HRA_E2E_CHROMIUM_ARGS='["--no-sandbox"]' \
 *   node tests/settings-screenshots.cjs [outputDir]
 */
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const path = require('node:path');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}
const outDir = path.resolve(process.argv[2] || path.join(__dirname, '..', '..', 'doc', 'ui-review', 'r6'));
fs.mkdirSync(outDir, { recursive: true });

const json = (r, body, status = 200) => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

const SETTINGS = [
  {
    key: 'deadline_soon_days', value: 7, default: 7, min: 1, max: 60,
    label: 'Số ngày báo trước khi hết hạn ứng tuyển',
    description: 'Vị trí còn ít hơn hoặc bằng số ngày này sẽ hiện việc "Vị trí sắp hết hạn ứng tuyển" trên Dashboard.',
  },
  {
    key: 'waiting_attention_days', value: 7, default: 7, min: 1, max: 90,
    label: 'Số ngày hồ sơ được tính là chờ lâu',
    description: 'Hồ sơ đang sàng lọc lâu hơn số ngày này được đếm vào dòng "hồ sơ chờ quá N ngày" trên Dashboard và được tô đậm trong danh sách ứng viên.',
  },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'screenshot');
    localStorage.setItem('hra_locale', 'vi');
  });
  await context.route('**/v1/**', async r => {
    const url = new URL(r.request().url());
    const p = url.pathname;
    if (p === '/v1/auth/me') return json(r, { user_id: 'admin', display_name: 'Quản trị', system_roles: ['ADMIN'], position_assignments: [] });
    if (p === '/v1/admin/settings' && r.request().method() === 'GET') return json(r, { settings: SETTINGS });
    // The admin screen loads AI configuration alongside; answer with the shape
    // the page expects so the settings tab can be reached without a backend.
    if (p === '/v1/admin/ai/active-config') return json(r, { config: {}, source: 'environment', allowed_by_this_process: false });
    if (p === '/v1/admin/ai/options') return json(r, { providers: [], models: [], endpoints: [], external_api_allowed: false, api_key_encryption_ready: false });
    if (p.startsWith('/v1/admin/')) return json(r, {});
    return json(r, {});
  });

  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  // Standalone route: the settings tab inside /admin also loads AI configuration,
  // which needs a full mock of that shape. The screen under review is the same
  // component either way.
  await page.goto(`${base}/admin/settings`, { waitUntil: 'networkidle' });
  await page.getByTestId('hr-settings').waitFor({ timeout: 15000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(outDir, '04-hr-settings-desktop.png'), fullPage: true });
  console.log('saved 04-hr-settings-desktop.png');

  // Phone size: the two-line row must wrap without overlapping the save button.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(outDir, '05-hr-settings-mobile.png'), fullPage: true });
  console.log('saved 05-hr-settings-mobile.png');

  await browser.close();
  if (errors.length) console.log('PAGE ERRORS:', [...new Set(errors)].join(' | '));
})().catch(err => { console.error(err); process.exit(1); });
