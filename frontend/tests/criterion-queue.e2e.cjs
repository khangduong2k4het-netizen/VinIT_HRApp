/**
 * Duyệt một tiêu chí trên nhiều hồ sơ: mỗi dòng một hồ sơ cùng trích dẫn của
 * tiêu chí đang chọn, xác nhận/sai ngay tại dòng, mở hồ sơ đầy đủ khi cần.
 *
 * Trước đây muốn xác minh tiêu chí c2 trên chục hồ sơ, HR phải mở từng hồ sơ,
 * cuộn tới đúng tiêu chí đó, bấm, quay lại danh sách — mười lần lặp cho một
 * quyết định giống nhau.
 *
 * Fixture: ranking p1 có 12 hồ sơ đang xét tuyển, mỗi hồ sơ mang kết quả của cả
 * bốn tiêu chí; c2/c3 cần xác minh, c1/c4 thì không.
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
    localStorage.setItem('hra_access_token', 'criterion-queue');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const reviews = [];
  const detailRequests = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/assessments\/results\/.+\/review$/.test(path) && request.method() === 'POST') {
      reviews.push({ resultId: path.split('/results/')[1].split('/')[0], body: JSON.parse(request.postData() || '{}') });
    }
    if (/^\/v1\/applications\/app-\d+$/.test(path)) detailRequests.push(path);
  });

  // --- 1. Lối vào từ danh sách ứng viên ------------------------------------
  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();
  await page.getByTestId('review-by-criterion').click();

  // --- 2. Mở ra đúng tiêu chí đang có việc, danh sách dựng từ ranking ------
  await page.getByTestId('criterion-select').waitFor({ timeout: 10000 });
  assert.match(page.url(), /\/positions\/p1\/applicants\/by-criterion$/, 'mở đúng màn duyệt theo tiêu chí');
  assert.match(await page.getByTestId('criterion-select').innerText(), /Thiết kế cơ sở dữ liệu quan hệ/, 'mặc định chọn tiêu chí đang chờ xác minh');
  assert.match(await page.getByTestId('criterion-queue-progress').innerText(), /Đã xác minh 0\/12 hồ sơ/);
  assert.match(await page.getByTestId('criterion-queue-count').innerText(), /Hiển thị 8\/12 hồ sơ/, 'chỉ tải trang đầu');

  const firstRow = page.getByTestId('criterion-row-app-0');
  await firstRow.waitFor();
  assert.match(await firstRow.innerText(), /Nguyễn Minh Anh/, 'mỗi dòng một hồ sơ');
  assert.match(await page.getByTestId('criterion-quote-app-0').innerText(), /composite index cho bảng events/, 'trích dẫn của tiêu chí đang chọn');
  assert.match(await firstRow.innerText(), /Trang 3/);
  assert.match(await page.getByTestId('criterion-outcome-app-0').innerText(), /Đáp ứng/);
  assert.equal(await page.getByTestId('criterion-confirm-app-0').isEnabled(), true, 'tiêu chí đang chờ thì cho xác nhận');

  // --- 3. Xác nhận tại chỗ, chỉ hồ sơ đó đổi trạng thái --------------------
  await page.getByTestId('criterion-confirm-app-0').click();
  await page.getByTestId('criterion-reviewed-app-0').waitFor();
  assert.match(await page.getByTestId('criterion-reviewed-app-0').innerText(), /Đã xác nhận/);
  assert.equal(await page.getByTestId('criterion-confirm-app-0').isDisabled(), true, 'đã kiểm rồi thì không ghi thêm lần nữa');
  assert.match(await page.getByTestId('criterion-queue-progress').innerText(), /Đã xác minh 1\/12 hồ sơ/);
  assert.equal(await page.getByTestId('criterion-confirm-app-1').isEnabled(), true, 'hồ sơ khác vẫn đang chờ');
  assert.deepEqual(reviews.map(entry => [entry.resultId, entry.body.decision]), [['app-0:r-c2', 'CONFIRMED']], 'ghi đúng kết quả của hồ sơ đó');

  // --- 4. Tiêu chí không bị gắn cờ thì không cho thao tác ------------------
  await page.locator('[data-testid="criterion-select"] [role="combobox"]').click();
  await page.getByRole('option', { name: /Kinh nghiệm Python/ }).click();
  await page.getByTestId('criterion-not-required-app-1').waitFor();
  assert.equal(await page.getByTestId('criterion-confirm-app-1').isDisabled(), true, 'tiêu chí không cần xác minh');
  assert.match(await page.getByTestId('criterion-queue-progress').innerText(), /0\/0 hồ sơ/, 'tiêu chí này không có hồ sơ nào bị gắn cờ');
  assert.equal(reviews.length, 1, 'đổi tiêu chí không ghi gì');

  // --- 5. Quay lại tiêu chí cũ: quyết định vừa rồi vẫn còn -----------------
  await page.locator('[data-testid="criterion-select"] [role="combobox"]').click();
  await page.getByRole('option', { name: /Thiết kế cơ sở dữ liệu quan hệ/ }).click();
  assert.match(await page.getByTestId('criterion-reviewed-app-0').innerText(), /Đã xác nhận/);

  // --- 6. Đánh dấu sai phải kèm lý do --------------------------------------
  await page.getByTestId('criterion-reject-app-1').click();
  const rejectConfirm = page.getByTestId('criterion-reject-confirm');
  await rejectConfirm.waitFor();
  assert.equal(await rejectConfirm.isDisabled(), true, 'chưa nêu lý do thì không ghi được');
  await page.getByTestId('criterion-reject-reason').fill('CV chỉ nêu tên bảng, không có số liệu trước/sau tối ưu.');
  await rejectConfirm.click();
  await page.getByTestId('criterion-reviewed-app-1').waitFor();
  assert.match(await page.getByTestId('criterion-reviewed-app-1').innerText(), /Đã đánh dấu sai/);
  assert.deepEqual(
    reviews.map(entry => [entry.resultId, entry.body.decision, entry.body.comment]),
    [
      ['app-0:r-c2', 'CONFIRMED', undefined],
      ['app-1:r-c2', 'REJECTED', 'CV chỉ nêu tên bảng, không có số liệu trước/sau tối ưu.'],
    ],
  );
  assert.match(await page.getByTestId('criterion-queue-progress').innerText(), /Đã xác minh 2\/12 hồ sơ/);

  // --- 7. Mở hồ sơ đầy đủ từ đúng dòng -------------------------------------
  const profileHref = await page.getByTestId('criterion-open-profile-app-1').getAttribute('href');
  assert.equal(profileHref, '/positions/p1/applicants/app-1#criterion-c2', 'mở đúng hồ sơ, không kèm hàng đợi lạ');
  assert.ok(!/[?&](queue|sort)=/.test(profileHref), 'link không được gắn hàng đợi của màn duyệt theo tiêu chí');

  // --- 8. Trang sau, và chỉ tải chi tiết hồ sơ đang hiện -------------------
  assert.ok(detailRequests.length <= 8, `chưa bấm tải thêm mà đã gọi ${detailRequests.length} hồ sơ`);
  await page.getByTestId('criterion-load-more').click();
  await page.getByTestId('criterion-row-app-11').waitFor();
  assert.match(await page.getByTestId('criterion-queue-count').innerText(), /Hiển thị 12\/12 hồ sơ/);
  assert.ok(detailRequests.length <= 12, 'tải thêm mới gọi thêm hồ sơ, không gọi lại cả loạt');

  assert.deepEqual(unexpected, [], `không có request lạ: ${unexpected.join(', ')}`);
  await browser.close();
  console.log('Criterion queue: entry, ranking-backed rows, in-place confirm/reject, full-profile link, pending-only actions: OK');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
