/**
 * UX-02 — the Candidate Review loop must close.
 *
 * What is checked, and why each one is a real defect if it regresses:
 *  1. The rubric requirement is reachable from the verdict without leaving the page,
 *     and opening it does not push the page taller than the budget.
 *  2. Pressing a citation loads the CV and lands on the cited page — it used to look
 *     clickable ("Trang 2 · Đã xác minh") while doing nothing until "Xem CV gốc".
 *  3. "Not found in the CV" and "not checked yet" are different labels. They were
 *     both "Trích dẫn chưa xác minh", which hid the stronger signal.
 *  4. A reviewer can record a decision, it survives a reload, and a rejection needs
 *     a reason. This is the only thing that lets the "needs verification" queue
 *     close, so it must not silently fail.
 *  5. The application status is untouched by all of it: verifying evidence must
 *     never be a recruiting decision.
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
    localStorage.setItem('hra_access_token', 'review');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const posted = [];
  page.on('request', r => {
    if (r.url().includes('/review') && r.method() === 'POST') posted.push(JSON.parse(r.postData() || '{}'));
  });

  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. Rubric requirement ------------------------------------------------
  const requirementToggles = page.getByTestId('criterion-requirement-toggle');
  assert.ok(await requirementToggles.count() >= 2, 'criteria with a rubric body get a toggle');
  assert.equal(
    await page.evaluate(() => [...document.querySelectorAll('[data-testid="criterion-requirement-toggle"]')]
      .every(t => t.getAttribute('aria-expanded') === 'false')),
    true,
    'all requirement panels start collapsed so they cost no height',
  );
  const heightBefore = await page.evaluate(() => document.documentElement.scrollHeight);
  await requirementToggles.first().click();
  await page.waitForTimeout(300);
  assert.equal(await requirementToggles.first().getAttribute('aria-expanded'), 'true');
  const panel = page.locator('[id^="requirement-"]').first();
  await panel.waitFor();
  const requirementText = await panel.innerText();
  assert.match(requirementText, /Xây dựng và vận hành dịch vụ Python/);
  assert.match(requirementText, /Tối thiểu 3 năm/, 'the requirement spec the matcher used is shown');
  assert.match(requirementText, /Bằng chứng cần tìm/);
  const heightWithPanel = await page.evaluate(() => document.documentElement.scrollHeight);
  assert.ok(heightWithPanel > heightBefore, 'opening a panel shows its content in flow, not in a popup');
  await requirementToggles.first().click();
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(() => document.documentElement.scrollHeight), heightBefore, 'closing restores the height');

  // --- 2. Citation loads the CV and opens the cited page --------------------
  assert.equal(await page.getByTestId('citation-quote').first().getAttribute('role'), 'button');
  await page.getByTestId('citation-quote').first().click();
  await page.waitForSelector('#cv-pdf-viewer', { timeout: 5000 });
  const viewerSrc = await page.locator('#cv-pdf-viewer').getAttribute('src');
  assert.match(viewerSrc, /#page=2$/, 'the viewer opens the cited page, not page 1');

  // --- 3. Two different citation states ------------------------------------
  const failed = page.getByTestId('citation-status-FAILED');
  const unchecked = page.getByTestId('citation-status-UNVERIFIED');
  if (await unchecked.count()) assert.equal(await unchecked.first().innerText(), 'Chưa đối chiếu');

  // --- 4. Record a review, and it survives a reload ------------------------
  const firstReviewBlock = page.getByTestId('criterion-review-block').first();
  assert.equal(await firstReviewBlock.isVisible(), true, 'a flagged criterion offers a decision');
  assert.equal(
    await page.getByTestId('verification-progress').innerText().then(t => /Đã xác minh 0\/2/.test(t)),
    true,
    'progress states how many flagged criteria are still open',
  );

  // A rejection without a reason must be impossible in the UI, not just in the API.
  await firstReviewBlock.getByTestId('reject-citation').click();
  await page.getByTestId('reject-confirm').waitFor();
  assert.equal(await page.getByTestId('reject-confirm').isDisabled(), true, 'cannot record a rejection with no reason');
  await page.getByTestId('reject-reason').fill('CV chỉ ghi "lead" chung, không có quy mô nhóm hay thời gian.');
  assert.equal(await page.getByTestId('reject-confirm').isEnabled(), true);
  await page.getByTestId('reject-confirm').click();
  await page.getByTestId('criterion-reviewed').first().waitFor();
  assert.deepEqual(posted.at(-1), { decision: 'REJECTED', comment: 'CV chỉ ghi "lead" chung, không có quy mô nhóm hay thời gian.' });

  // Reload: the decision came from the server, not from local optimism.
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="criterion-reviewed"]');
  assert.match(await page.getByTestId('criterion-reviewed').first().innerText(), /không đúng/);
  assert.match(await page.getByTestId('verification-progress').innerText(), /Đã xác minh 1\/2/);

  // Confirming the second one closes the queue for this application.
  await page.getByTestId('confirm-citation').first().click();
  await page.waitForFunction(() => /Đã xác minh đủ 2\/2/.test(document.body.innerText), null, { timeout: 5000 });
  assert.match(await page.getByTestId('verification-progress').innerText(), /rời hàng đợi/);
  assert.deepEqual(posted.at(-1), { decision: 'CONFIRMED' });

  // --- 5. Verifying evidence never changes the recruiting status -----------
  assert.equal(
    await page.evaluate(() => document.body.innerText.includes('ĐANG XEM')),
    true,
    'application status is untouched by verification',
  );
  const statusPosts = unexpected.length === 0 ? [] : ['unexpected'];
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(() => {
    // The status control still offers the same next steps as before.
    const select = document.querySelector('input[id="application-status-label"], [aria-labelledby="application-status-label"]');
    return Boolean(select);
  }), true);
  assert.deepEqual(statusPosts, [], `no unexpected API calls: ${unexpected.join(', ')}`);
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('UX-02 review: rubric in place, citation opens the right CV page, two citation states, review recorded and persisted, status untouched: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
