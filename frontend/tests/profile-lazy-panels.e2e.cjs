/**
 * Mở hồ sơ không được trả giá cho những khối chưa ai đọc.
 *
 * Profile ứng viên và lịch sử trạng thái là hai accordion đóng sẵn ở dưới trang.
 * Trước đây cả hai tự tải ngay khi mở hồ sơ (mỗi lần mở tốn thêm 2 request, và
 * profile còn bị tải lặp khi panel mount lại). Nay chúng chỉ tải ở lần mở đầu
 * tiên, đúng một lần.
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
    localStorage.setItem('hra_access_token', 'lazy-panels');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const requests = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/v1\/applications\/app-0\/(profile|status-events)$/.test(path)) requests.push(path);
  });

  await page.goto(`${base}/positions/p1/applicants/app-0?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.getByTestId('sticky-pending').waitFor({ timeout: 15000 });
  await page.waitForTimeout(600);

  assert.deepEqual(requests, [], `mở hồ sơ không được tải khối đang đóng (đã gọi: ${requests.join(', ')})`);

  // Mở profile: đúng một lần tải, và có nội dung.
  await page.locator('.MuiAccordionSummary-content', { hasText: 'Profile ứng viên' }).first().click();
  await page.waitForFunction(() => document.body.innerText.includes('phiên bản 1'), null, { timeout: 10000 });
  assert.equal(requests.filter(path => path.endsWith('/profile')).length, 1, 'mở profile tải đúng một lần');

  // Đóng rồi mở lại: không tải lại.
  await page.locator('.MuiAccordionSummary-content', { hasText: 'Profile ứng viên' }).first().click();
  await page.locator('.MuiAccordionSummary-content', { hasText: 'Profile ứng viên' }).first().click();
  await page.waitForTimeout(500);
  assert.equal(requests.filter(path => path.endsWith('/profile')).length, 1, 'đóng/mở lại không tải lại profile');

  // Lịch sử trạng thái cũng vậy.
  await page.locator('.MuiAccordionSummary-content', { hasText: 'Lịch sử trạng thái' }).first().click();
  await page.waitForFunction(() => document.body.innerText.includes('trạng thái'), null, { timeout: 10000 });
  await page.waitForTimeout(500);
  assert.equal(requests.filter(path => path.endsWith('/status-events')).length, 1, 'mở lịch sử tải đúng một lần');

  assert.deepEqual(unexpected, [], `không có request lạ: ${unexpected.join(', ')}`);
  await browser.close();
  console.log('Profile lazy panels: không tải khi đóng, tải đúng một lần khi mở, không tải lại khi đóng/mở: OK');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
