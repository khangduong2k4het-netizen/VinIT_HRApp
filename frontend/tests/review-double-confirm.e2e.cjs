/**
 * Hai lần bấm `1` sát nhau trên cùng một tiêu chí chỉ được ghi một review.
 *
 * Trước đây đường bàn phím không biết `reviewSaving`: tiêu chí vẫn hiện là
 * "chưa xác minh" cho tới khi backend trả lời, nên cú bấm thứ hai trong lúc
 * request đầu còn bay gửi thêm một POST `CONFIRMED` cho đúng tiêu chí đó. Review
 * là dòng append-only, nên lịch sử của tiêu chí có hai quyết định của cùng một
 * người ở cùng một thời điểm.
 *
 * Mock giữ mỗi POST review 700ms để hai lần bấm chắc chắn rơi vào lúc đang lưu —
 * nếu không, test chỉ đang đo tốc độ mạng chứ không đo chốt chặn.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const reviewDelayMs = 700;

const activeCriterion = page => page.evaluate(() => {
  const card = document.querySelector('[data-testid="evidence-card"][data-active="true"]');
  return card ? card.id.replace(/^criterion-/, '') : null;
});

const progress = page => page.evaluate(() => {
  const chip = document.querySelector('[data-testid="verification-progress"]');
  const match = (chip?.textContent || '').match(/Đã xác minh (?:đủ )?(\d+)\/(\d+)/);
  return match ? `${match[1]}/${match[2]}` : null;
});

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'double-confirm');
    localStorage.setItem('hra_locale', 'vi');
  });

  // Mọi lần ghi review đều đi qua đây, nên đếm được chính xác số dòng mà backend
  // sẽ nhận — kể cả khi một lần bấm bị bỏ qua ở phía trình duyệt.
  const reviewRequests = [];
  const slowReview = async route => {
    const body = JSON.parse(route.request().postData() || '{}');
    reviewRequests.push({
      resultId: new URL(route.request().url()).pathname.split('/').slice(-2)[0],
      decision: body.decision,
      at: Date.now(),
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
        created_at: '2026-11-21T09:15:00Z',
      }),
    });
  };
  const unexpected = await installMockApi(context, {
    '/v1/assessments/results/r-c2/review': slowReview,
    '/v1/assessments/results/r-c3/review': slowReview,
  });

  const page = await context.newPage();
  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');
  assert.equal(await activeCriterion(page), 'c2', 'con trỏ bắt đầu ở tiêu chí chờ đầu tiên');

  // --- 1. Bấm `1` hai lần trong lúc request đầu còn bay -------------------
  await page.keyboard.press('1');
  await page.keyboard.press('1');
  // Lần bấm thứ hai rơi vào lúc request đầu còn đang giữ (700ms), nên nó phải bị
  // bỏ qua: nếu không, chỗ này sẽ có hai dòng review cho cùng một tiêu chí.
  await page.waitForTimeout(100);
  assert.equal(reviewRequests.length, 1, 'lần bấm thứ hai trong lúc đang lưu không gửi thêm request nào');

  await page.waitForFunction(
    () => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''),
    undefined,
    { timeout: 8000 },
  );
  await page.waitForTimeout(200);
  assert.equal(reviewRequests.length, 1, 'vẫn đúng một review sau khi request đầu xong');
  assert.equal(reviewRequests[0].resultId, 'r-c2', 'review được ghi cho tiêu chí đang chọn');
  assert.equal(await progress(page), '1/2', 'tiến độ chỉ cộng một lần, không phải hai');
  assert.equal(await activeCriterion(page), 'c3', 'con trỏ nhảy đúng một lần, sang tiêu chí còn chờ');

  // --- 2. Nút chuột cũng chỉ ghi một lần ----------------------------------
  // Hai cú bấm phải xảy ra trong **cùng một tác vụ JS**, trước lần render kế
  // tiếp. Bấm `click({ force: true })` hai lần từ ngoài thì không chứng minh
  // được gì: cú thứ hai rơi vào lúc React đã disable nút, trình duyệt không
  // phát sự kiện click, nên test vẫn xanh dù không có khoá nào.
  const clickTwiceInOneTask = await page.evaluate(() => {
    const button = document.querySelector('[data-testid="sticky-confirm"]');
    if (!button) throw Error('không thấy nút Xác nhận trên thanh dính');
    const enabledBefore = !button.disabled;
    button.click();
    // Đọc lại ngay trước cú thứ hai: nếu React đã kịp disable thì cú này bị
    // trình duyệt chặn và phép kiểm không chứng minh được gì — phải báo lỗi.
    const enabledForSecond = !button.disabled;
    button.click();
    return { enabledBefore, enabledForSecond };
  });
  assert.equal(clickTwiceInOneTask.enabledBefore, true, 'nút Xác nhận đang bật trước khi bấm đôi');
  assert.equal(
    clickTwiceInOneTask.enabledForSecond,
    true,
    'cú bấm thứ hai phải tới được handler; nếu nút đã disable thì phép kiểm này vô nghĩa',
  );
  // 100ms < 700ms của request đầu, nên chỗ này phải vẫn đúng một review mới.
  await page.waitForTimeout(120);
  assert.equal(reviewRequests.length, 2, 'cú bấm chuột thứ hai trong lúc đang lưu không gửi thêm POST');
  await page.waitForFunction(
    () => /Đã xác minh đủ 2\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''),
    undefined,
    { timeout: 8000 },
  );
  await page.waitForTimeout(200);
  assert.equal(reviewRequests.length, 2, 'chỉ thêm đúng một review cho tiêu chí thứ hai');
  assert.deepEqual(
    reviewRequests.map(request => request.resultId),
    ['r-c2', 'r-c3'],
    'mỗi tiêu chí đúng một review, không có dòng trùng',
  );
  assert.equal(await progress(page), '2/2');
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('Double keypress while a review is saving writes one review and jumps the cursor once: OK');
  await page.close();
  await context.close();
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
