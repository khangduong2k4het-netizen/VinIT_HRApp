/**
 * A bulk batch must survive closing the tab.
 *
 * A 30–50 application batch with one dropped connection used to leave HR with no
 * record of what had been written and no list of what failed, and closing the tab
 * lost even the banner. This test covers the two recovery paths:
 *  1. A real batch that fails on one record is stored; after a reload the page
 *     says a batch is unfinished, reopens the same per-row record (reason, stopping
 *     point), and retrying touches only the failed record.
 *  2. A record that was being written when the tab died comes back as "outcome
 *     unknown" with a pointer to the profile, never as a silent retry.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const STORAGE_KEY = 'hra-bulk-run:p1';

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  // --- 1. A failed batch is kept, and retry runs only the failure -----------
  let shortlistAttempts = 0;
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'bulk-recovery');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context, {
    '/v1/applications/app-11/status': async r => {
      const body = JSON.parse(r.request().postData() || '{}');
      if (body.new_status === 'SHORTLIST' && shortlistAttempts === 0) {
        shortlistAttempts += 1;
        return r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Mất kết nối tới máy chủ.' }) });
      }
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ application_id: 'app-11', application_status: body.new_status }) });
    },
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));
  const retryCalls = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    const match = path.match(/^\/v1\/applications\/(app-\d+)\/status$/);
    if (match && request.method() === 'PATCH') retryCalls.push([match[1], JSON.parse(request.postData() || '{}').new_status]);
  });
  const box = name => page.getByRole('checkbox', { name: `Chọn hồ sơ ${name}` });

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  assert.equal(await page.getByTestId('bulk-run-recovered').count(), 0, 'no recovery banner on a clean first visit');

  await box('Lê Thu Hà').check(); // app-2, IN_REVIEW, succeeds
  await box('Phan Trọng Nghĩa').check(); // app-11, NEW, fails at SHORTLIST
  await page.getByTestId('bulk-action-bar').waitFor();
  await page.getByTestId('bulk-shortlist-open').click();
  await page.getByTestId('bulk-dialog').waitFor();
  await page.getByTestId('bulk-confirm').click();
  await page.getByTestId('bulk-failure-summary').waitFor({ timeout: 20000 });
  assert.match(await page.getByTestId('bulk-row-error-app-11').innerText(), /Mất kết nối/);

  // The failure is written to storage while the dialog is still open.
  const saved = await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY);
  assert.ok(saved, 'a batch with leftovers must be stored');
  assert.equal(JSON.parse(saved).version, 1);

  // Closing the tab and coming back keeps the record and says what is left.
  await page.getByTestId('bulk-dialog').getByRole('button', { name: 'Đóng' }).click();
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  const banner = page.getByTestId('bulk-run-recovered');
  await banner.waitFor();
  assert.match(await banner.innerText(), /Lô Shortlist lần trước chưa xong: 1\/2 hồ sơ đã cập nhật, 1 lỗi, 0 chưa rõ kết quả/);

  await page.getByTestId('bulk-run-open').click();
  await page.getByTestId('bulk-dialog').waitFor();
  assert.match(await page.getByTestId('bulk-row-error-app-11').innerText(), /Mất kết nối/);
  assert.match(await page.getByTestId('bulk-row-state-app-2').innerText(), /Xong/);

  retryCalls.length = 0;
  await page.getByTestId('bulk-retry').click();
  await page.getByTestId('bulk-dialog').waitFor({ state: 'detached', timeout: 20000 });
  assert.deepEqual(retryCalls, [['app-11', 'SHORTLIST']], 'the retry after a reload runs only the failed record');
  assert.equal(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY), null, 'a finished batch is cleared from storage');

  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  assert.equal(await page.getByTestId('bulk-run-recovered').count(), 0, 'nothing to recover once the batch finished');
  assert.deepEqual(pageErrors, [], `no client-side exceptions: ${pageErrors.join(' | ')}`);
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  await context.close();

  // --- 2. A record interrupted mid-write comes back as unknown --------------
  const interruptedContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const interruptedPage = await interruptedContext.newPage();
  const interruptedUnexpected = await installMockApi(interruptedContext);
  const interruptedErrors = [];
  interruptedPage.on('pageerror', error => interruptedErrors.push(String(error)));
  await interruptedPage.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'bulk-interrupted');
    localStorage.setItem('hra_locale', 'vi');
  });
  await interruptedPage.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await interruptedPage.waitForSelector('[data-testid="applicant-count"]');
  // The tab died while writing the second step of this New record, so its outcome
  // is genuinely unknown — not "failed", and not safe to resend automatically.
  await interruptedPage.evaluate(key => localStorage.setItem(key, JSON.stringify({
    version: 1,
    position_id: 'p1',
    mode: 'shortlist',
    reason: '',
    saved_at: Date.now(),
    rows: [
      {
        application_id: 'app-2', candidate_name: 'Lê Thu Hà', from_status: 'IN_REVIEW',
        steps: ['SHORTLIST'], applied: 1, reached_status: 'SHORTLIST', state: 'done', error: null,
      },
      {
        application_id: 'app-11', candidate_name: 'Phan Trọng Nghĩa', from_status: 'NEW',
        steps: ['IN_REVIEW', 'SHORTLIST'], applied: 1, reached_status: 'IN_REVIEW', state: 'running', error: null,
      },
    ],
  })), STORAGE_KEY);
  await interruptedPage.reload({ waitUntil: 'networkidle' });
  await interruptedPage.waitForSelector('[data-testid="applicant-count"]');

  const interruptedBanner = interruptedPage.getByTestId('bulk-run-recovered');
  await interruptedBanner.waitFor();
  assert.match(await interruptedBanner.innerText(), /1\/2 hồ sơ đã cập nhật, 0 lỗi, 1 chưa rõ kết quả/);
  await interruptedPage.getByTestId('bulk-run-open').click();
  await interruptedPage.getByTestId('bulk-dialog').waitFor();
  assert.match(await interruptedPage.getByTestId('bulk-row-state-app-11').innerText(), /Chưa rõ kết quả/);
  assert.match(await interruptedPage.getByTestId('bulk-row-interrupted-app-11').innerText(), /Lô bị gián đoạn khi đang ghi hồ sơ này/);
  assert.equal(await interruptedPage.getByTestId('bulk-retry').count(), 0, 'an unknown outcome is never retried automatically');
  assert.equal(await interruptedPage.getByRole('link', { name: 'Mở hồ sơ' }).count(), 1, 'HR gets a way to check that application');

  await interruptedPage.getByTestId('bulk-dialog').getByRole('button', { name: 'Đóng' }).click();
  await interruptedBanner.waitFor();
  await interruptedPage.getByTestId('bulk-run-dismiss').click();
  assert.equal(await interruptedPage.getByTestId('bulk-run-recovered').count(), 0, 'dismissing clears the stored record');
  assert.equal(await interruptedPage.evaluate(key => localStorage.getItem(key), STORAGE_KEY), null);
  assert.deepEqual(interruptedErrors, [], `no client-side exceptions: ${interruptedErrors.join(' | ')}`);
  assert.deepEqual(interruptedUnexpected, [], `all API calls are accounted for: ${interruptedUnexpected.join(', ')}`);
  await interruptedContext.close();

  console.log('Bulk recovery: a failed batch is stored and restored after a reload with its per-row reasons, retry touches only the failure, and a record interrupted mid-write returns as "unknown" with a profile link instead of being retried: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
