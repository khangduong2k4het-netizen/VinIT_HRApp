/**
 * Hai hồ sơ bị gắn cờ trùng phải quyết được khi nhìn cạnh nhau.
 *
 * Trước đây cách duy nhất là mở hồ sơ A, đọc, quay lại danh sách, mở hồ sơ B rồi
 * so trong đầu: định danh, CV và cả bốn tiêu chí. Màn so sánh đặt hai bên cạnh
 * nhau, mỗi bên một khung CV với con trỏ trang riêng.
 *
 * Fixture: DUPLICATE_SIGNALS có đúng một cặp app-3/app-9 (SAME_EMAIL, 0.92);
 * hai bên khác nhau ở c1, c2, c3 và giống nhau ở c4.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const cvPages = page => page.$$eval('#cv-pdf-viewer', frames => frames.map(frame => {
  const match = (frame.getAttribute('src') || '').match(/#page=(\d+)/);
  return match ? Number(match[1]) : null;
}));

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'compare');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const cvRequests = [];
  page.on('request', request => {
    if (/\/cv-file$/.test(new URL(request.url()).pathname)) cvRequests.push(request.url());
  });

  // --- 1. Lối vào nằm ngay trên dòng bị gắn cờ ------------------------------
  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();
  const compareLink = page.locator('table').getByTestId('compare-pair-app-3-app-9');
  await compareLink.waitFor();
  assert.equal(
    new URL(await compareLink.getAttribute('href'), base).pathname + new URL(await compareLink.getAttribute('href'), base).search,
    '/positions/p1/applicants/compare?left=app-3&right=app-9',
    'link mở đúng cặp trong cảnh báo trùng',
  );
  await compareLink.click();

  // --- 2. Định danh hai bên, và lý do bị gắn cờ ----------------------------
  await page.getByTestId('compare-left').waitFor({ timeout: 10000 });
  const left = page.getByTestId('compare-left');
  const right = page.getByTestId('compare-right');
  assert.match(await left.innerText(), /Phạm Đình Khang/);
  assert.match(await right.innerText(), /Dương Hồng Yến/);
  assert.match(await page.getByTestId('compare-left-email').innerText(), /khang\.pham@example\.com/);
  assert.match(await page.getByTestId('compare-right-email').innerText(), /yen\.duong@example\.com/);
  assert.match(await page.getByTestId('compare-signal').innerText(), /Cùng email/);
  assert.match(await page.getByTestId('compare-signal').innerText(), /92%/);
  assert.match(await page.getByTestId('compare-differing').innerText(), /Khác kết luận ở 3\/4 tiêu chí/);

  // Hai hồ sơ mở được từ đây, đúng hồ sơ của từng bên.
  assert.match(await page.getByTestId('compare-left-open').getAttribute('href'), /\/positions\/p1\/applicants\/app-3$/);
  assert.match(await page.getByTestId('compare-right-open').getAttribute('href'), /\/positions\/p1\/applicants\/app-9$/);

  // --- 3. Kết quả tiêu chí: dòng khác kết luận được đánh dấu --------------
  for (const criterion of ['c1', 'c2', 'c3', 'c4']) {
    assert.equal(await page.getByTestId(`compare-criterion-${criterion}`).count(), 1, `${criterion} có dòng riêng`);
  }
  assert.equal(await page.getByTestId('compare-differs-c1').count(), 1);
  assert.equal(await page.getByTestId('compare-differs-c2').count(), 1);
  assert.equal(await page.getByTestId('compare-differs-c3').count(), 1);
  assert.equal(await page.getByTestId('compare-differs-c4').count(), 0, 'c4 giống nhau nên không bị đánh dấu khác');
  assert.match(await page.getByTestId('compare-criterion-c1').getByTestId('compare-outcome-left').innerText(), /Đáp ứng/);
  assert.match(await page.getByTestId('compare-criterion-c1').getByTestId('compare-outcome-right').innerText(), /Đáp ứng tốt/);

  // --- 4. CV chỉ tải khi được yêu cầu, và mỗi bên nhảy trang riêng --------
  assert.equal(cvRequests.length, 0, 'mở màn so sánh chưa tải CV nào');
  assert.deepEqual(await cvPages(page), []);

  await page.getByTestId('compare-criterion-c2').getByTestId('compare-open-page-left').click();
  await page.waitForFunction(() => document.querySelectorAll('#cv-pdf-viewer').length === 1, undefined, { timeout: 8000 });
  assert.deepEqual(await cvPages(page), [3], 'trích dẫn bên trái mở trang 3 của CV bên trái');
  assert.equal(cvRequests.length, 1, 'chỉ CV bên trái được tải');

  await page.getByTestId('compare-criterion-c3').getByTestId('compare-open-page-right').click();
  await page.waitForFunction(() => document.querySelectorAll('#cv-pdf-viewer').length === 2, undefined, { timeout: 8000 });
  assert.deepEqual(await cvPages(page), [3, 5], 'bên phải mở trang 5, bên trái vẫn ở trang 3');
  assert.equal(cvRequests.length, 2, 'mỗi bên chỉ tải CV của mình, một lần');

  // --- 5. Điều hướng trang độc lập bằng nút của từng khung ----------------
  await page.getByRole('button', { name: 'Trang sau' }).first().click();
  await page.waitForTimeout(300);
  assert.deepEqual(await cvPages(page), [4, 5], 'nút trang của khung trái không kéo khung phải theo');

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Duplicate compare: entry from the flagged row, identities, verdict differences, per-side CV pages: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
