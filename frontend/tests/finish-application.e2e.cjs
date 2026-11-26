/**
 * "Đã xử lý xong hồ sơ này" — the review loop closes in one action.
 *
 * The three steps used to be separate: confirm each citation, open the status
 * dropdown, confirm the dialog, then click "Hồ sơ tiếp theo". None of them is
 * removed here; they are gathered into one action that keeps the same APIs and
 * the same transition matrix.
 *
 * What is checked, because each would be a real defect if it regressed:
 *  1. The profile offers exactly one finish action.
 *  2. Finishing records verification for the flagged criteria, and it is NOT
 *     possible to record "I checked" without attesting to it.
 *  3. Advancing keeps the queue context and carries the `completed` flag so the
 *     next profile can confirm the hop.
 *  4. Verification alone never changes the recruiting status.
 *  5. When a status change is chosen, a rejection still requires a reason, and
 *     the PATCH body is the one the existing API expects.
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
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'finish');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const reviewPosts = [];
  const statusPatches = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/review$/.test(path) && request.method() === 'POST') {
      reviewPosts.push(JSON.parse(request.postData() || '{}'));
    }
    if (/^\/v1\/applications\/app-\d+\/status$/.test(path) && request.method() === 'PATCH') {
      statusPatches.push(JSON.parse(request.postData() || '{}'));
    }
  });

  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. One finish action on the profile ---------------------------------
  assert.equal(await page.getByTestId('finish-application').count(), 1, 'the profile offers one finish action');
  await page.getByTestId('finish-application').click();
  const dialog = page.getByTestId('finish-dialog');
  await dialog.waitFor();

  // --- 2. The commitment is the button itself, and a status is preselected --
  assert.match(await page.getByTestId('finish-pending').innerText(), /Còn 2 tiêu chí/);
  assert.equal(await page.getByTestId('finish-attest').count(), 0, 'no separate checkbox to tick before confirming');
  assert.match(await page.getByTestId('finish-attest-note').innerText(), /đã đối chiếu 2 tiêu chí/);
  assert.equal(await page.getByTestId('finish-confirm').isDisabled(), false, 'the main button is the attestation, so it is pressable');
  assert.match(await page.getByTestId('finish-confirm').innerText(), /Xác nhận đã kiểm 2 tiêu chí/, 'the button says what pressing it attests to');
  assert.match(await page.getByTestId('finish-status').innerText(), /Shortlist/, 'the suggested status is already chosen');
  assert.match(await page.getByTestId('finish-suggestion').innerText(), /Điểm tổng hợp 69%/);

  // --- 3 + 4. Finish records verification, changes no status, advances -----
  // The suggestion must stay only a suggestion: ask for "keep the status" and
  // the finish must not touch application_status.
  await page.getByTestId('finish-status').locator('[role="combobox"]').click();
  await page.getByRole('option', { name: 'Giữ nguyên trạng thái' }).click();
  await page.getByTestId('finish-confirm').click();
  await page.waitForURL(/\/applicants\/app-8\?/, { timeout: 10000 });
  const next = new URL(page.url());
  assert.equal(next.searchParams.get('completed'), '1', 'the arrival carries a confirmation flag');
  assert.equal(next.searchParams.get('queue'), 'NEEDS_VERIFICATION', 'the queue context survives the hop');
  assert.deepEqual(reviewPosts.map(post => post.decision), ['CONFIRMED', 'CONFIRMED']);
  assert.equal(statusPatches.length, 0, 'verification alone never changes the recruiting status');
  assert.match(await page.getByTestId('action-feedback-success').innerText(), /hồ sơ trước/);
  assert.match(await page.evaluate(() => document.body.innerText), /app-8|Ngô Thanh Tùng/);

  // --- 5. A chosen status is still explicit, and a rejection needs a reason -
  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.getByTestId('finish-application').click();
  await dialog.waitFor();
  assert.equal(await page.getByTestId('finish-pending').count(), 0, 'nothing is pending after the recorded reviews');
  assert.match(await page.getByTestId('finish-status').innerText(), /Shortlist/, 'a suggestion is preselected on reopen too');
  await page.getByTestId('finish-status').locator('[role="combobox"]').click();
  await page.getByRole('option', { name: 'Loại vòng sàng lọc' }).click();
  assert.equal(await page.getByTestId('finish-confirm').isDisabled(), true, 'a rejection without a reason stays blocked');
  await page.getByLabel('Lý do loại hồ sơ').fill('Không đáp ứng yêu cầu bắt buộc về số năm kinh nghiệm.');
  await page.waitForFunction(() => !document.querySelector('[data-testid="finish-confirm"]').disabled);
  await page.getByTestId('finish-confirm').click();
  await page.waitForURL(/\/applicants\/app-8\?/, { timeout: 10000 });
  assert.equal(statusPatches.length, 1, 'exactly one status change, through the existing endpoint');
  assert.equal(statusPatches[0].new_status, 'REJECTED_SCREENING');
  assert.match(statusPatches[0].reason, /số năm kinh nghiệm/);

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Finish application: one action records verification, optional status with reason, then advances with a confirmation banner: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
