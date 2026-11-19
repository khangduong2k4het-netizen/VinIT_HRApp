/**
 * A reviewer who may change status but NOT record criterion reviews.
 *
 * That is the shape of a global ADMIN's access: `can_update_status` is true while
 * the review endpoint's gate (the HR-notes capability) is false. The screen used
 * to show the confirm/reject buttons anyway, so pressing one produced a 403. With
 * one capabilities object the buttons follow the review gate itself:
 *  1. No confirm/reject button on a flagged criterion, and the card says it is
 *     waiting for HR.
 *  2. The finish action still exists for the status half of the loop, and its
 *     dialog says evidence review is not permitted instead of asking for an
 *     attestation it cannot record.
 *  3. Finishing records no review and calls no review endpoint.
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
    localStorage.setItem('hra_access_token', 'status-only');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const forbidden = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/review$/.test(path) && request.method() === 'POST') forbidden.push(path);
  });

  await page.goto(`${base}/positions/p1/applicants/app-admin`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. No verification controls without the review capability -----------
  const blocks = page.getByTestId('criterion-review-block');
  assert.ok(await blocks.count() > 0, 'the fixture has flagged criteria');
  assert.equal(await page.getByTestId('confirm-citation').count(), 0, 'no confirm button without the review gate');
  assert.equal(await page.getByTestId('reject-citation').count(), 0, 'no reject button without the review gate');
  assert.match(await blocks.first().innerText(), /chờ HR xác minh/);

  // --- 2. Finish still works for the status half of the loop ---------------
  assert.equal(await page.getByTestId('finish-application').count(), 1, 'a status-only reviewer can still finish');
  await page.getByTestId('finish-application').click();
  const dialog = page.getByTestId('finish-dialog');
  await dialog.waitFor();
  assert.equal(await page.getByTestId('finish-no-review-permission').count(), 1, 'the dialog says verification is not permitted');
  assert.equal(await page.getByTestId('finish-attest').count(), 0, 'no attestation for work this reviewer cannot record');
  assert.equal(await page.getByTestId('finish-status').count(), 1, 'the status picker is still available');

  // --- 3. Finishing sends no review request --------------------------------
  await page.getByTestId('finish-confirm').click();
  await page.waitForURL(/completed=1/, { timeout: 10000 });
  assert.deepEqual(forbidden, [], 'no review POST may be attempted without the review gate');

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Status-only reviewer: verification controls hidden, finish explained, no 403-producing review call: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
