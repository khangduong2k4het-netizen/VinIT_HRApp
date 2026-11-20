/**
 * Measuring the UX work itself.
 *
 * The dashboard used to show only queue sizes, so "this felt better" could not be
 * checked. This test drives the real dashboard with a seeded local event log and
 * checks that:
 *  1. The impact block turns the log into median time in a profile, open-to-finish
 *     time and bulk usage. The server's overdue figure is shown once, in the work
 *     queue above, and is not repeated in the impact block.
 *  2. Clearing the measurements empties only this module's key.
 *  3. Opening a profile really records an open/leave pair with only the
 *     application id and a duration — no candidate name, no CV content.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi, workQueue, detail } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const STORAGE_KEY = 'hra-ux-events';
const now = Date.now();

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  // Máy chủ trả số hồ sơ quá hạn; phần còn lại của block là số đo cục bộ.
  const unexpected = await installMockApi(context, {
    '/v1/dashboard/work-queue': r => r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...workQueue,
        summary: {
          ...workQueue.summary,
          applications_waiting_over_threshold: 6,
          waiting_attention_days: 7,
          oldest_waiting_days: 23,
        },
      }),
    }),
  });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'ux');
    localStorage.setItem('hra_locale', 'vi');
  });

  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));

  // --- 1. The seeded log becomes readable numbers --------------------------
  // Gieo event một lần (không qua addInitScript, nếu không mỗi lần điều hướng lại
  // gieo lại và không kiểm được nút xoá).
  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  const block = page.getByTestId('ux-impact');
  await block.waitFor();
  await page.evaluate(({ key, events }) => localStorage.setItem(key, JSON.stringify(events)), {
    key: STORAGE_KEY,
    events: [
      { type: 'PROFILE_OPENED', at: now - 30 * 60_000, application_id: 'app-1' },
      { type: 'PROFILE_CLOSED', at: now - 27 * 60_000, application_id: 'app-1', duration_ms: 150_000 },
      { type: 'VERIFICATION_COMPLETED', at: now - 10 * 60_000, application_id: 'app-1' },
      { type: 'BULK_RUN', at: now - 60 * 60_000, duration_ms: 240_000, records: 12, failed: 1 },
    ],
  });
  await page.reload({ waitUntil: 'networkidle' });
  await block.waitFor();
  assert.match(await page.getByTestId('ux-median-dwell').innerText(), /^2\.5 phút$/, 'median time in a profile');
  assert.match(await page.getByTestId('ux-completion').innerText(), /^20 phút$/, 'time from first open to finishing');
  // The overdue figure belongs to the work queue above; the impact block must not
  // repeat it as a second, competing copy of the same server number.
  await page.getByText('6 hồ sơ chờ quá 7 ngày · lâu nhất 23 ngày').waitFor();
  assert.equal(await block.getByTestId('ux-overdue').count(), 0, 'the impact block no longer repeats the overdue figure');
  assert.doesNotMatch(await block.innerText(), /lâu nhất|Quá 7 ngày/);
  assert.match(await page.getByTestId('ux-bulk').innerText(), /^1$/, 'one bulk run');
  await block.getByText('12 hồ sơ · 1 lỗi · trung bình 4 phút').waitFor();

  // --- 2. Clearing measurements stays local -------------------------------
  await page.getByTestId('ux-clear').click();
  await page.waitForFunction(key => localStorage.getItem(key) === null, STORAGE_KEY);
  assert.equal(await page.evaluate(() => localStorage.getItem('hra_access_token')), 'ux', 'clearing leaves the session alone');
  assert.match(await block.innerText(), /Chưa có số đo nào: số liệu xuất hiện sau khi bạn mở hồ sơ hoặc chạy một lô\./);

  // --- 3. Opening a profile records only an id and a duration --------------
  await page.goto(`${base}/positions/p1/applicants/app-2`, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: detail.candidate_name }).first().waitFor({ timeout: 20000 }).catch(() => {});
  await page.waitForFunction(key => {
    const events = JSON.parse(localStorage.getItem(key) || '[]');
    return events.some(event => event.type === 'PROFILE_OPENED');
  }, STORAGE_KEY);
  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  const recorded = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]'), STORAGE_KEY);
  const opened = recorded.find(event => event.type === 'PROFILE_OPENED');
  const closed = recorded.find(event => event.type === 'PROFILE_CLOSED');
  assert.equal(opened.application_id, 'app-2');
  assert.ok(closed, 'leaving the profile records the leave event');
  assert.equal(closed.application_id, 'app-2');
  assert.ok(closed.duration_ms >= 0, 'the leave event carries the time spent');
  assert.deepEqual(Object.keys(opened).sort(), ['application_id', 'at', 'type']);
  const raw = await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY);
  assert.doesNotMatch(raw, /Nguyễn|email|@/, 'no candidate name or contact detail is stored');
  // The block now reflects this session's single visit instead of the seeded log.
  await page.getByTestId('ux-impact').waitFor();
  assert.match(await page.getByTestId('ux-median-dwell').innerText(), /phút|Chưa có số đo/);

  assert.deepEqual(pageErrors, [], `no client-side exceptions: ${pageErrors.join(' | ')}`);
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  console.log('UX impact: seeded events show median profile time, open-to-finish time and bulk usage without repeating the work queue’s overdue count, clearing stays local to this module, and opening a profile records only an application id plus duration: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
