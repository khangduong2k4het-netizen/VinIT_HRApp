/**
 * Nhánh "hồ sơ trượt tiêu chí bắt buộc" khi hoàn tất hồ sơ.
 *
 * Đây là nhánh dễ sai nhất của hộp thoại hoàn tất: hồ sơ có một tiêu chí
 * MUST_HAVE kết luận NO_MATCH, nên đề xuất đúng là "Loại vòng sàng lọc" — và
 * loại hồ sơ thì bắt buộc phải có lý do. Trước đây nhánh này chỉ có unit test
 * cho suggestFinishStatus(), không có đường nào chạy qua giao diện thật, nên
 * không ai kiểm được rằng: hộp thoại chọn sẵn đúng trạng thái, nút hoàn tất vẫn
 * bị chặn cho tới khi nhập lý do, và chưa có PATCH trạng thái nào được gửi.
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
    localStorage.setItem('hra_access_token', 'mandatory-fail');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const reviewPosts = [];
  const statusPatches = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/review$/.test(path) && request.method() === 'POST') reviewPosts.push(JSON.parse(request.postData() || '{}'));
    if (path === '/v1/applications/app-must-fail/status' && request.method() === 'PATCH') {
      statusPatches.push(JSON.parse(request.postData() || '{}'));
    }
  });

  await page.goto(`${base}/positions/p1/applicants/app-must-fail`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. Hộp thoại chọn sẵn "Loại vòng sàng lọc" -------------------------
  await page.getByTestId('finish-application').click();
  await page.getByTestId('finish-dialog').waitFor();
  assert.match(
    await page.getByTestId('finish-status').innerText(),
    /Loại vòng sàng lọc/,
    'a failed mandatory criterion preselects screening rejection',
  );
  assert.match(
    await page.getByTestId('finish-suggestion').innerText(),
    /Có tiêu chí bắt buộc chưa đạt/,
    'the dialog says why that status is suggested, and that the reason is still HR input',
  );
  assert.match(await page.getByTestId('finish-pending').innerText(), /Còn 1 tiêu chí/, 'the failed criterion still awaits HR verification');

  // --- 2. Nút hoàn tất bị chặn cho tới khi có lý do -----------------------
  const confirm = page.getByTestId('finish-confirm');
  assert.equal(await confirm.isDisabled(), true, 'rejecting without a reason is blocked');
  assert.match(await confirm.innerText(), /Xác nhận đã kiểm 1 tiêu chí và hoàn tất/, 'the button says what it attests to');

  const reasonField = page.getByLabel('Lý do loại hồ sơ');
  await reasonField.fill('   ');
  await page.waitForTimeout(200);
  assert.equal(await confirm.isDisabled(), true, 'whitespace is not a reason');

  // --- 3. Chưa có PATCH trạng thái nào được gửi ---------------------------
  assert.equal(statusPatches.length, 0, 'opening the dialog must not change the status by itself');
  assert.equal(reviewPosts.length, 0, 'opening the dialog must not record a review either');
  // Bấm vào nút đang bị chặn không được làm gì (đây là chỗ dễ lọt nếu chỉ ẩn nút).
  await confirm.click({ force: true }).catch(() => {});
  await page.waitForTimeout(300);
  assert.equal(statusPatches.length, 0, 'pressing the blocked button sends no status change');
  assert.equal(reviewPosts.length, 0, 'pressing the blocked button records no review');

  // --- 4. Nhập lý do thì mới gửi, và gửi đúng thứ -------------------------
  await reasonField.fill('Trượt tiêu chí bắt buộc: không có kinh nghiệm Python cho dịch vụ production.');
  await page.waitForFunction(() => !document.querySelector('[data-testid="finish-confirm"]').disabled, undefined, { timeout: 5000 });
  await confirm.click();
  await page.waitForURL(url => !url.pathname.includes('app-must-fail'), { timeout: 10000 });

  assert.equal(statusPatches.length, 1, 'exactly one status change is sent');
  assert.equal(statusPatches[0].new_status, 'REJECTED_SCREENING', 'the failed mandatory criterion rejects at screening');
  assert.match(statusPatches[0].reason, /tiêu chí bắt buộc/, 'the typed reason travels with the status change');
  assert.deepEqual(reviewPosts.map(post => post.decision), ['CONFIRMED'], 'the failed criterion is verified before the status changes');

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  console.log('Mandatory-fail finish: screening rejection preselected, blocked until a reason, no status change before that: OK');
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
