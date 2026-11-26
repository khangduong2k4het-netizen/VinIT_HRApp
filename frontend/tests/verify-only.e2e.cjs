/**
 * Finishing a profile when the reviewer may verify evidence but NOT change the
 * application status.
 *
 * The review endpoint gates on the HR-notes capability, while the finish action
 * used to be gated on `can_update_status`. A reviewer with only the first
 * permission could therefore never close the review loop. Now:
 *  1. The finish action is available when the user can verify criteria OR change
 *     status.
 *  2. The status picker is hidden when they cannot change status, and the dialog
 *     says the status stays as it is.
 *  3. Finishing still records the verification (with the attestation), sends no
 *     status PATCH, and moves on with the completion flag.
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
    localStorage.setItem('hra_access_token', 'verify-only');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const reviewPosts = [];
  const statusPatches = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/review$/.test(path) && request.method() === 'POST') reviewPosts.push(JSON.parse(request.postData() || '{}'));
    if (/\/applications\/[^/]+\/status$/.test(path) && request.method() === 'PATCH') statusPatches.push(path);
  });

  await page.goto(`${base}/positions/p1/applicants/app-verifier`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. The finish action exists for a verify-only reviewer --------------
  assert.equal(await page.getByTestId('finish-application').count(), 1, 'verify-only reviewers can close the loop');
  await page.getByTestId('finish-application').click();
  const dialog = page.getByTestId('finish-dialog');
  await dialog.waitFor();

  // --- 2. No status picker, and the dialog says why ------------------------
  assert.equal(await page.getByTestId('finish-status').count(), 0, 'no status picker without the status permission');
  assert.match(await page.getByTestId('finish-no-status-permission').innerText(), /giữ nguyên trạng thái/);
  assert.equal(await page.getByTestId('finish-attest').count(), 0, 'the commitment is the button, not a separate checkbox');
  assert.match(await page.getByTestId('finish-confirm').innerText(), /Xác nhận đã kiểm 2 tiêu chí/);
  assert.equal(await page.getByTestId('finish-confirm').isDisabled(), false, 'pressing the button is the attestation');

  // --- 3. Verification is recorded, status untouched, then move on --------
  await page.getByTestId('finish-confirm').click();
  await page.waitForURL(/\/applicants\?.*completed=1/, { timeout: 10000 });
  assert.deepEqual(reviewPosts.map(post => post.decision), ['CONFIRMED', 'CONFIRMED']);
  assert.deepEqual(statusPatches, [], 'a verify-only reviewer must not call the status endpoint');
  // The list rewrites its own URL on mount, so the completed flag is read from
  // the arrival URL that waitForURL matched rather than from the final one.
  assert.match(await page.url(), /\/positions\/p1\/applicants(\?|$)/);

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Verify-only finish: action available, no status picker, verification recorded with attestation, no status change, completion flag kept: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
