/**
 * One vocabulary for both queue screens, no developer jargon, and dates that
 * follow the language the user picked.
 *
 *  1. Dashboard "Việc cần làm" is grouped into the three business clusters:
 *     Cần tôi xử lý / Cần tôi quyết / Đã quyết.
 *  2. The ranking chips use the same three clusters and the same wording for the
 *     same work ("Cần kiểm tra file", "Cần xác minh", "Cảnh báo trùng").
 *  3. No screen says "matching" any more — it is developer vocabulary, not HR's.
 *  4. With the language set to English, a date renders in en-US order, not the
 *     hard-coded Vietnamese one (and vice versa).
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

  // --- 1 + 2 + 3. Shared clusters and wording, no "matching" ---------------
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'vocabulary');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#work-queue');
  const actionCluster = page.getByTestId('work-cluster-ACTION');
  const decisionCluster = page.getByTestId('work-cluster-DECISION');
  const doneCluster = page.getByTestId('work-cluster-DONE');
  assert.match(await actionCluster.innerText(), /Cần tôi xử lý/);
  assert.match(await decisionCluster.innerText(), /Cần tôi quyết/);
  assert.match(await doneCluster.innerText(), /Đã quyết/);
  // Same wording as the ranking chip, on the dashboard side.
  assert.match(await actionCluster.innerText(), /Cần kiểm tra file/);
  assert.match(await actionCluster.innerText(), /Cần xác minh/);
  assert.match(await actionCluster.innerText(), /Cảnh báo trùng/);
  assert.match(await decisionCluster.innerText(), /Tiêu chí chờ HM duyệt/);
  assert.match(await doneCluster.innerText(), /Đã xác minh xong 3 hồ sơ/);

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();
  for (const cluster of ['ACTION', 'DECISION', 'DONE']) {
    await page.getByTestId(`queue-cluster-${cluster}`).waitFor();
  }
  assert.match(await page.getByTestId('queue-cluster-ACTION').innerText(), /Cần tôi xử lý/);
  assert.match(await page.getByTestId('queue-cluster-DECISION').innerText(), /Cần tôi quyết/);
  assert.match(await page.getByTestId('queue-cluster-DONE').innerText(), /Đã quyết/);
  assert.match(await page.getByTestId('queue-cluster-ACTION').innerText(), /Cần kiểm tra file/);
  assert.match(await page.getByTestId('queue-cluster-ACTION').innerText(), /Cảnh báo trùng/);
  assert.match(await page.getByTestId('queue-cluster-DONE').innerText(), /Đã shortlist/);

  const rankingText = await page.evaluate(() => document.body.innerText);
  assert.doesNotMatch(rankingText, /\bmatching\b/i, 'developer jargon "matching" must be gone from the ranking screen');
  assert.match(rankingText, /Mức phù hợp/, 'the table header uses business wording');

  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  const dashboardText = await page.evaluate(() => document.body.innerText);
  assert.doesNotMatch(dashboardText, /\bmatching\b/i, 'developer jargon "matching" must be gone from the dashboard');
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  await context.close();

  // --- 4. Dates follow the selected language ------------------------------
  // /careers-demo renders a deadline through the shared date locale, so it is
  // the cheapest honest check of the formatting (25/11 in vi, 11/25 in en).
  const jobs = [{
    position_id: 'p9', position_code: 'REQ-2026-099', title: 'Backend Engineer',
    org_unit: 'Nền tảng', work_location: 'Hà Nội', work_mode: 'Hybrid', employment_type: 'Full-time',
    application_deadline_at: '2026-11-25T08:30:00Z', description: 'Mô tả công việc.', can_apply: true,
  }];
  const datesFor = async locale => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addInitScript(l => {
      localStorage.setItem('hra_access_token', 'dates');
      localStorage.setItem('hra_locale', l);
    }, locale);
    await ctx.route('**/v1/careers-demo/jobs', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(jobs) }));
    const p = await ctx.newPage();
    await p.goto(`${base}/careers-demo`, { waitUntil: 'networkidle' });
    await p.getByText(/Hạn:/).waitFor();
    const text = await p.getByText(/Hạn:/).innerText();
    await ctx.close();
    return text;
  };
  assert.match(await datesFor('vi'), /25\/11\/2026/, 'Vietnamese keeps day-first order');
  assert.match(await datesFor('en'), /11\/25\/2026/, 'English uses month-first order, not the hard-coded vi-VN one');

  console.log('Vocabulary: three shared clusters on dashboard and ranking, same wording per task, no "matching" in UI, dates follow the selected language: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
