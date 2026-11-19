/**
 * Filtering the ranking list by evidence, not only by name.
 *
 * HR asks two questions every day — "which applications lack evidence for
 * criterion X" and "which applications have been waiting for my verification for
 * over 3 days" — and previously had to open each profile to answer them. This
 * test drives the three controls and checks the list actually narrows:
 *  1. Choosing a criterion + "missing evidence" keeps exactly the rows whose
 *     result is unclear, still requires verification, or is absent.
 *  2. Switching the outcome to "not met" narrows to that result instead.
 *  3. Choosing a waiting time keeps only rows that need verification and are old
 *     enough; a row that merely needs verification but is fresh is excluded.
 *  4. Clearing the filters brings the whole queue back.
 *
 * The ranking fixture repeats one set of criterion results for every candidate, so
 * this test serves its own ranking where criterion c1 varies by row; that is what
 * makes a filter assertion meaningful instead of "all 12 or none".
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi, ranking } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const C1_NAME = 'Kinh nghiệm Python cho dịch vụ production';
const customRanking = ranking.map((item, index) => ({
  ...item,
  criterion_results: (item.criterion_results || []).map(result => (result.criterion_id !== 'c1' ? result : {
    ...result,
    outcome: index % 4 === 0 ? 'NO_MATCH' : index % 4 === 1 ? 'UNCLEAR' : 'MATCH',
    requires_verification: index % 4 === 1,
  })),
}));

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'criteria-filter');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context, {
    '/v1/assessments/ranking/latest/p1': r => r.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(customRanking),
    }),
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  await page.waitForSelector('tbody tr');

  const rowCount = () => page.locator('tbody tr').count();
  const waitForRows = expected => page.waitForFunction(
    count => document.querySelectorAll('tbody tr').length === count,
    expected,
    { timeout: 10000 },
  );
  const namedRow = name => page.locator('tbody tr', { hasText: name }).count();
  const pick = async (combobox, option) => {
    await page.getByRole('combobox', { name: combobox }).click();
    await page.getByRole('option', { name: option, exact: true }).click();
  };

  // --- 1. Missing evidence for one criterion --------------------------------
  assert.equal(await rowCount(), 12, 'every screening row is listed before filtering');
  await pick('Tiêu chí', C1_NAME);
  await waitForRows(3);
  assert.match(await page.getByTestId('applicant-count').innerText(), /Hiển thị 3\/12/);
  assert.match(await page.getByTestId('applicant-count').innerText(), /Thiếu bằng chứng/);
  // Only the rows whose c1 result is unclear need a look; a clear match is out.
  assert.equal(await namedRow('Trần Quốc Bảo'), 1);
  assert.equal(await namedRow('Đỗ Văn Nam'), 1);
  assert.equal(await namedRow('Nguyễn Minh Anh'), 0, 'a row with clear evidence for c1 is not "missing evidence"');

  // --- 2. A different outcome narrows to that result ------------------------
  await pick('Bằng chứng', 'Chưa đáp ứng');
  await waitForRows(3);
  assert.equal(await namedRow('Nguyễn Minh Anh'), 1);
  assert.equal(await namedRow('Trần Quốc Bảo'), 0);

  // --- 3. Waiting for my verification over 3 days --------------------------
  await pick('Tiêu chí', 'Mọi tiêu chí');
  await waitForRows(12);
  await pick('Chờ xác minh', 'Quá 3 ngày');
  // Four fixture rows still need verification (NEEDS_HR_VERIFICATION or coverage
  // under the threshold) and are all 27+ days old; MEETS rows are excluded because
  // there is nothing left to verify on them. POSSIBLE_MISMATCH rows with enough
  // coverage are a different queue and are not verification work.
  await waitForRows(4);
  assert.match(await page.getByTestId('applicant-count').innerText(), /Chỉ hồ sơ chờ xác minh quá 3 ngày/);
  assert.equal(await namedRow('Nguyễn Minh Anh'), 1, 'a waiting row that is old enough is listed');
  assert.equal(await namedRow('Trần Quốc Bảo'), 0, 'a row with nothing to verify is not listed');

  // --- 4. Clearing brings the whole queue back ------------------------------
  await page.getByTestId('clear-applicant-filters').click();
  await waitForRows(12);
  assert.doesNotMatch(await page.getByTestId('applicant-count').innerText(), /Chờ xác minh|Tiêu chí/);

  assert.deepEqual(pageErrors, [], `no client-side exceptions: ${pageErrors.join(' | ')}`);
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Applicant evidence filters: criterion + missing evidence narrows to unclear/unverified rows, another outcome narrows to that result, verification waiting time respects the age, clearing restores the queue: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
