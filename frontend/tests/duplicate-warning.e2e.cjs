/**
 * Duplicate warnings must not be a dead end.
 *
 * Before: a row could say "Hồ sơ trùng lặp" with no name, and the only way to
 * learn who it duplicated was to scroll to the bottom card and press "Tải cảnh
 * báo trùng". Now the counterpart name and a link to that profile sit on the
 * flagged row, and the signal list loads by itself — both on the whole list and
 * when entering the duplicate queue.
 *
 * Checked here:
 *  1. The flagged row shows the counterpart by name, without pressing anything.
 *  2. The duplicate signal list is fetched automatically, once per view.
 *  3. The counterpart link opens that application's profile.
 *  4. The duplicate queue loads its signals automatically too, and holds only
 *     the flagged rows, each naming its counterpart.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'duplicate');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  let duplicateRequests = 0;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/v1/positions/p1/duplicate-signals') duplicateRequests += 1;
  });

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();

  // --- 1 + 2. Counterpart on the row, loaded without a click ----------------
  // Both the desktop table and the mobile cards render this block; the table is
  // the one on screen at this viewport.
  const flaggedRow = page.locator('table').getByTestId('duplicate-counterpart-app-3');
  await flaggedRow.waitFor();
  assert.match(await flaggedRow.innerText(), /Trùng với:\s*Dương Hồng Yến/, 'the flagged row names the other application');
  assert.equal(duplicateRequests, 1, 'the signal list is fetched automatically, once');

  // --- 3. The name is a link to that profile -------------------------------
  await flaggedRow.getByRole('link', { name: 'Mở hồ sơ đối ứng Dương Hồng Yến' }).click();
  await page.waitForURL(/\/applicants\/app-9(\?|$)/, { timeout: 10000 });
  await page.getByText('Dương Hồng Yến').first().waitFor();

  // --- 4. The duplicate queue loads by itself and stays narrow -------------
  const beforeQueue = duplicateRequests;
  await page.goto(`${base}/positions/p1/applicants?queue=DUPLICATE`, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => decodeURIComponent(location.search).includes('queue=DUPLICATE'));
  await page.locator('table').getByTestId('duplicate-counterpart-app-9').waitFor();
  assert.equal(duplicateRequests, beforeQueue + 1, 'entering the queue loads the signals without pressing the bottom button');
  assert.match(await page.locator('table').getByTestId('duplicate-counterpart-app-9').innerText(), /Trùng với:\s*Phạm Đình Khang/);
  assert.equal(await page.locator('table tbody tr').count(), 2, 'the duplicate queue holds exactly the flagged applications');
  assert.equal(await page.locator('table').getByTestId('duplicate-counterpart-app-0').count(), 0, 'an unflagged row shows no duplicate block');

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Duplicate warning: counterpart name and profile link on the flagged row, signals loaded automatically on the list and in the duplicate queue: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
