/**
 * Hai cú bấm sát nhau trên màn duyệt theo tiêu chí chỉ được ghi một review.
 *
 * Màn `by-criterion` cũng gọi `reviewCriterionResult`, và ở đây nút Xác nhận /
 * Ghi lại chỉ bị disable bằng state `saving` — state chỉ đổi sau khi React vẽ
 * lại, nên hai cú bấm trong cùng một nhịp đều thấy "chưa lưu" và cùng gửi POST.
 * Review là bảng append-only: hai POST là hai dòng quyết định cho cùng một tiêu
 * chí của cùng một người.
 *
 * Test bấm hai lần **trong một tác vụ JS** (cả hai xảy ra trước lần render đầu),
 * nên nút khi đó vẫn đang enabled — nếu chốt chặn chỉ dựa vào `disabled` thì
 * test sẽ thấy hai request. Mock giữ mỗi POST 700ms để lần bấm thứ hai chắc
 * chắn rơi vào lúc request đầu còn bay.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const reviewDelayMs = 700;

const doubleClickInOneTask = (page, testId) => page.evaluate(id => {
  const button = document.querySelector(`[data-testid="${id}"]`);
  if (!button) throw Error(`không thấy nút ${id}`);
  button.click();
  button.click();
}, testId);

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'by-criterion-double');
    localStorage.setItem('hra_locale', 'vi');
  });

  // Mọi POST review đi qua đây, nên đếm được đúng số dòng backend sẽ nhận.
  const reviewRequests = [];
  const slowReview = async route => {
    const body = JSON.parse(route.request().postData() || '{}');
    reviewRequests.push({
      resultId: decodeURIComponent(new URL(route.request().url()).pathname.split('/').slice(-2)[0]),
      decision: body.decision,
      comment: body.comment || null,
    });
    await new Promise(resolve => setTimeout(resolve, reviewDelayMs));
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        review_id: `rev-${reviewRequests.length}`,
        decision: body.decision,
        comment: body.comment || null,
        reviewer_user_id: 'u-hr',
        reviewer_name: 'Nguyễn Thu Hằng',
        created_at: '2026-11-23T09:15:00Z',
      }),
    });
  };
  const unexpected = await installMockApi(context, {
    '/v1/assessments/results/app-0:r-c2/review': slowReview,
    '/v1/assessments/results/app-1:r-c2/review': slowReview,
  });

  const page = await context.newPage();
  await page.goto(`${base}/positions/p1/applicants/by-criterion`, { waitUntil: 'networkidle' });
  const confirmFirst = page.getByTestId('criterion-confirm-app-0');
  await confirmFirst.waitFor({ timeout: 10000 });
  assert.equal(await confirmFirst.isEnabled(), true, 'dòng app-0 đang chờ xác minh');

  // --- 1. Nút Xác nhận: hai cú bấm trong cùng một tác vụ -------------------
  await doubleClickInOneTask(page, 'criterion-confirm-app-0');
  // Nút bị disable chỉ sau lần render kế tiếp, nên ở đây cú bấm thứ hai đã thật
  // sự tới handler — chốt chặn phải nằm ở ref, không phải ở thuộc tính disabled.
  await page.waitForTimeout(120);
  assert.equal(reviewRequests.length, 1, 'cú bấm thứ hai trong lúc đang lưu không gửi thêm POST');

  await page.getByTestId('criterion-reviewed-app-0').waitFor({ timeout: 8000 });
  await page.waitForTimeout(200);
  assert.equal(reviewRequests.length, 1, 'vẫn đúng một review sau khi request đầu xong');
  assert.deepEqual(
    reviewRequests.map(entry => [entry.resultId, entry.decision]),
    [['app-0:r-c2', 'CONFIRMED']],
    'review được ghi cho đúng kết quả của dòng đó',
  );
  assert.match(await page.getByTestId('criterion-queue-progress').innerText(), /Đã xác minh 1\/12 hồ sơ/);
  assert.match(await page.getByTestId('criterion-reviewed-app-0').innerText(), /Đã xác nhận/);

  // --- 2. Hộp thoại Đánh dấu sai: hai cú bấm vào "Ghi lại" ------------------
  await page.getByTestId('criterion-reject-app-1').click();
  await page.getByTestId('criterion-reject-reason').fill('CV chỉ nêu tên bảng, không có số đo trước/sau.');
  await page.getByTestId('criterion-reject-confirm').waitFor();
  await doubleClickInOneTask(page, 'criterion-reject-confirm');
  await page.waitForTimeout(120);
  assert.equal(reviewRequests.length, 2, 'đánh dấu sai cũng chỉ ghi một lần');

  await page.getByTestId('criterion-reviewed-app-1').waitFor({ timeout: 8000 });
  await page.waitForTimeout(200);
  assert.equal(reviewRequests.length, 2, 'không có dòng review thứ hai cho cùng tiêu chí');
  assert.deepEqual(
    reviewRequests.map(entry => [entry.resultId, entry.decision]),
    [['app-0:r-c2', 'CONFIRMED'], ['app-1:r-c2', 'REJECTED']],
    'mỗi hồ sơ đúng một quyết định, không trùng',
  );
  assert.equal(await page.getByTestId('criterion-reject-confirm').count(), 0, 'lưu xong thì hộp thoại đóng');

  assert.deepEqual(unexpected, [], `không có request lạ: ${unexpected.join(', ')}`);
  console.log('By-criterion double click: one review per decision for both confirm and reject: OK');
  await page.close();
  await context.close();
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
