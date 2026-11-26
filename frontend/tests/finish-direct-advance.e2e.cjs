/**
 * "Đã xử lý xong hồ sơ này" khi không còn gì để ghi.
 *
 * Khi mọi tiêu chí bị gắn cờ đã được xác minh và không có bước trạng thái nào để
 * ghi, hộp thoại hoàn tất chỉ để bấm thêm hai lần: "giữ nguyên trạng thái" đã
 * chọn sẵn, rồi bấm xác nhận. Nay nút đi thẳng sang hồ sơ kế trong hàng đợi.
 *
 * Ba nhánh, để không "sửa" luôn những trường hợp hộp thoại là cần thiết:
 *  1. `sạch`: không còn tiêu chí chờ, không có đề xuất trạng thái → **1** cú bấm,
 *     không POST/PATCH nào thêm, và hồ sơ kế nhận cờ `completed=1`.
 *  2. `còn-chờ`: còn 2 tiêu chí chưa xác minh → vẫn mở hộp thoại, chưa đi đâu.
 *  3. `đổi-trạng-thái`: hết tiêu chí chờ nhưng có đề xuất Shortlist → vẫn mở hộp
 *     thoại, vì ở đó mới có lựa chọn trạng thái.
 *
 * Nhánh 1 dùng một hồ sơ đã xong: mọi tiêu chí bị gắn cờ đã có review và trạng
 * thái đang ở bước không có đề xuất chuyển tiếp (INTERVIEW). Fixture mặc định
 * không có hồ sơ nào như vậy (mọi hồ sơ đều IN_REVIEW với điểm 69 → đề xuất
 * Shortlist), nên trạng thái đó phải dựng bằng override.
 *
 * Số cú bấm đếm bằng listener `click` pha capture trên `window`, tức cú bấm thật.
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/finish-direct-advance.e2e.cjs
 * In một dòng `FINISH_DIRECT {json}`.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi, detail: BASE_DETAIL } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

// Hồ sơ "đã xong": tiêu chí bị gắn cờ đã có review, trạng thái INTERVIEW không có
// đề xuất chuyển tiếp → không còn gì để ghi khi bấm "Đã xử lý xong".
const finishedDetail = {
  ...BASE_DETAIL,
  application_id: 'app-5',
  application_status: 'INTERVIEW',
  candidate_name: 'Đỗ Văn Nam',
  identity: { ...BASE_DETAIL.identity, display_name: 'Đỗ Văn Nam' },
  latest_assessment: {
    ...BASE_DETAIL.latest_assessment,
    application_id: 'app-5',
    matching_score: 58,
    criterion_results: BASE_DETAIL.latest_assessment.criterion_results.map(criterion => ({
      ...criterion,
      result_id: `app-5:${criterion.result_id}`,
      hr_reviews: criterion.requires_verification
        ? [{
          review_id: `seed-${criterion.criterion_id}`,
          decision: 'CONFIRMED',
          comment: null,
          reviewer_user_id: 'u-hr',
          reviewer_name: 'Nguyễn Thu Hằng',
          created_at: '2026-11-20T09:00:00Z',
        }]
        : [],
    })),
  },
};

const openProfile = async (browser, path, overrides = {}) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'finish-direct');
    localStorage.setItem('hra_locale', 'vi');
    window.__clicks = 0;
    window.addEventListener('click', () => { window.__clicks += 1; }, true);
  });
  const unexpected = await installMockApi(context, overrides);
  const page = await context.newPage();
  const reviewPosts = [];
  const statusPatches = [];
  page.on('request', request => {
    const requestPath = new URL(request.url()).pathname;
    if (/\/review$/.test(requestPath) && request.method() === 'POST') reviewPosts.push(JSON.parse(request.postData() || '{}'));
    if (/^\/v1\/applications\/app-\d+\/status$/.test(requestPath) && request.method() === 'PATCH') statusPatches.push(JSON.parse(request.postData() || '{}'));
  });
  await page.goto(`${base}${path}`, { waitUntil: 'networkidle' });
  return {
    context,
    page,
    reviewPosts,
    statusPatches,
    unexpected,
    clicks: () => page.evaluate(() => window.__clicks),
    resetClicks: () => page.evaluate(() => { window.__clicks = 0; }),
  };
};

const confirmFlaggedCriteria = async page => {
  await page.keyboard.press('1');
  await page.waitForFunction(
    () => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''),
    undefined,
    { timeout: 8000 },
  );
  await page.keyboard.press('1');
  await page.waitForFunction(
    () => /Đã xác minh đủ 2\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''),
    undefined,
    { timeout: 8000 },
  );
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  // --- 1. Sạch: một cú bấm là sang hồ sơ kế --------------------------------
  // Đi đúng đường HR đi: danh sách → mở hồ sơ, để ngữ cảnh hàng đợi (và hồ sơ kế)
  // có thật. Deep link trần không mang thứ tự hàng đợi nên không có "hồ sơ kế".
  const clean = await openProfile(browser, '/positions/p1/applicants?queue=NEEDS_VERIFICATION', {
    '/v1/applications/app-5': route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(finishedDetail) }),
  });
  const cleanPage = clean.page;
  await cleanPage.locator('table tbody tr a[href*="/applicants/app-5"]').first().click();
  await cleanPage.getByTestId('verification-progress').waitFor({ timeout: 15000 });
  await cleanPage.getByTestId('evidence-card').first().waitFor({ timeout: 15000 });
  assert.match(
    await cleanPage.getByTestId('verification-progress').innerText(),
    /2\/2/,
    'nhánh này phải bắt đầu ở hồ sơ đã xác minh đủ, nếu không thì phép đo vô nghĩa',
  );
  await clean.resetClicks();
  const reviewsBeforeFinish = clean.reviewPosts.length;
  const before = new URL(cleanPage.url()).pathname;
  await cleanPage.getByTestId('finish-application').click();
  await cleanPage.waitForURL(url => url.pathname !== before, { timeout: 10000 });
  const cleanClicks = await clean.clicks();
  const after = new URL(cleanPage.url());
  assert.equal(cleanClicks, 1, 'một cú bấm phải hoàn tất và chuyển hồ sơ, không mở hộp thoại');
  assert.match(after.pathname, /\/applicants\/app-\d+$/, `phải chuyển sang một hồ sơ khác, thấy ${after.pathname}`);
  assert.notEqual(after.pathname.split('/').pop(), 'app-5', 'phải rời hồ sơ vừa hoàn tất');
  assert.equal(after.searchParams.get('queue'), 'NEEDS_VERIFICATION', 'ngữ cảnh hàng đợi đi theo hồ sơ kế');
  assert.equal(clean.reviewPosts.length, reviewsBeforeFinish, 'hoàn tất không được ghi thêm review nào');
  assert.equal(clean.statusPatches.length, 0, 'không đổi trạng thái thì không được PATCH trạng thái');
  assert.equal(await cleanPage.getByTestId('finish-dialog').count(), 0, 'không mở hộp thoại hai bước');
  await cleanPage.getByTestId('action-feedback-success').waitFor({ timeout: 5000 });
  assert.match(await cleanPage.getByTestId('action-feedback-success').innerText(), /hồ sơ trước/, 'có một dòng xác nhận cho HR');
  // Cờ `completed` được dùng một lần rồi bỏ khỏi URL, để refresh không lặp lại thông báo.
  assert.equal(new URL(cleanPage.url()).searchParams.get('completed'), null, 'cờ completed phải được bỏ sau khi đã báo');

  // --- 2. Còn tiêu chí chờ: vẫn mở hộp thoại -------------------------------
  const pending = await openProfile(browser, '/positions/p1/applicants/app-6?queue=NEEDS_VERIFICATION');
  await pending.page.getByTestId('evidence-card').first().waitFor({ timeout: 15000 });
  await pending.resetClicks();
  const pendingPath = new URL(pending.page.url()).pathname;
  await pending.page.getByTestId('finish-application').click();
  await pending.page.getByTestId('finish-dialog').waitFor({ timeout: 5000 });
  assert.equal(await pending.clicks(), 1, 'còn tiêu chí chờ thì cú bấm mở hộp thoại');
  assert.equal(new URL(pending.page.url()).pathname, pendingPath, 'chưa xác minh xong thì không được chuyển hồ sơ');
  assert.match(await pending.page.getByTestId('finish-pending').innerText(), /Còn 2 tiêu chí/);
  assert.equal(pending.reviewPosts.length, 0, 'mở hộp thoại không ghi gì');
  await pending.page.keyboard.press('Escape');

  // --- 3. Hết tiêu chí chờ nhưng có đề xuất trạng thái: vẫn mở hộp thoại ----
  const statusArm = await openProfile(browser, '/positions/p1/applicants/app-0?queue=NEEDS_VERIFICATION');
  await statusArm.page.getByTestId('evidence-card').first().waitFor({ timeout: 15000 });
  await confirmFlaggedCriteria(statusArm.page);
  await statusArm.resetClicks();
  const statusPath = new URL(statusArm.page.url()).pathname;
  await statusArm.page.getByTestId('finish-application').click();
  await statusArm.page.getByTestId('finish-dialog').waitFor({ timeout: 5000 });
  assert.equal(await statusArm.clicks(), 1, 'có đề xuất trạng thái thì cú bấm mở hộp thoại');
  assert.equal(new URL(statusArm.page.url()).pathname, statusPath, 'chưa chọn trạng thái thì không được chuyển hồ sơ');
  assert.equal(await statusArm.page.getByTestId('finish-pending').count(), 0, 'nhánh này chỉ còn trạng thái để chọn');
  assert.match(await statusArm.page.getByTestId('finish-suggestion').innerText(), /Shortlist/);
  assert.equal(await statusArm.page.getByTestId('finish-confirm').isDisabled(), false, 'vẫn bấm được nút hoàn tất trong hộp thoại');

  console.log(`FINISH_DIRECT ${JSON.stringify({
    clean: { clicks: cleanClicks, reviewPostsAtFinish: clean.reviewPosts.length - reviewsBeforeFinish, statusPatches: clean.statusPatches.length, advancedTo: after.pathname },
    pending: { clicks: await pending.clicks(), openedDialog: true },
    statusChange: { clicks: await statusArm.clicks(), openedDialog: true },
  })}`);

  for (const arm of [clean, pending, statusArm]) {
    assert.deepEqual(arm.unexpected, [], `không có request lạ: ${arm.unexpected.join(', ')}`);
    await arm.context.close();
  }
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
