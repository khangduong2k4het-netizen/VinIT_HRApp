/**
 * "Xác nhận tất cả dòng đang hiện" trên màn duyệt theo tiêu chí.
 *
 * Câu hỏi đo: một quyết định giống nhau cho N hồ sơ tốn bao nhiêu cú bấm và bao
 * nhiêu POST, và HR có nhìn thấy trước sẽ ghi cho những hồ sơ nào không.
 *
 * Ba nhánh, cùng một tập dòng (tính từ DOM, không hard-code):
 *  - `bulk`: mở danh sách xem trước rồi bấm xác nhận → **2** cú bấm, N POST.
 *  - `one-by-one` (đối chứng): bấm từng dòng như trước đây → **N** cú bấm, N POST.
 *    Không có nhánh này thì con số 2 cú bấm không chứng minh được gì.
 *  - `double-click`: bấm hai lần vào nút xác nhận trong **một tác vụ JS** (cả hai
 *    xảy ra trước lần render kế tiếp) → vẫn N POST, không ghi gấp đôi.
 *
 * Số cú bấm đếm bằng listener `click` ở pha capture trên `window`, tức cú bấm
 * thật của người dùng, không phải số lần gọi hàm trong DOM.
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/by-criterion-confirm-all.e2e.cjs
 * In một dòng `CONFIRM_ALL {json}`.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const openScreen = async browser => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'confirm-all');
    localStorage.setItem('hra_locale', 'vi');
    window.__clicks = 0;
    window.addEventListener('click', () => { window.__clicks += 1; }, true);
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const posts = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (request.method() !== 'POST' || !url.pathname.endsWith('/review')) return;
    const body = JSON.parse(request.postData() || '{}');
    posts.push({ resultId: decodeURIComponent(url.pathname.split('/').slice(-2)[0]), decision: body.decision });
  });
  await page.goto(`${base}/positions/p1/applicants/by-criterion`, { waitUntil: 'networkidle' });
  await page.getByTestId('criterion-confirm-app-0').waitFor({ timeout: 15000 });
  // Chờ trích dẫn của mọi dòng đang hiện tải xong: trong lúc "đang tải" nút bị
  // disable, nên đọc sớm sẽ thấy ít dòng hơn thực tế và phép đo sai.
  await page.waitForFunction(() => {
    const buttons = Array.from(document.querySelectorAll('[data-testid^="criterion-confirm-app-"]'));
    return buttons.some(button => !button.disabled)
      && !document.body.innerText.includes('Đang tải trích dẫn của các hồ sơ đang hiện');
  }, null, { timeout: 15000 });
  await page.waitForTimeout(300);
  const confirmable = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="criterion-confirm-app-"]'))
    .filter(button => !button.disabled)
    .map(button => button.getAttribute('data-testid').replace('criterion-confirm-', '')));
  return { context, page, posts, unexpected, confirmable, clicks: () => page.evaluate(() => window.__clicks) };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  // --- 1. Một hành động cho N dòng ------------------------------------------
  const bulk = await openScreen(browser);
  const { page, posts, confirmable } = bulk;
  assert.ok(confirmable.length >= 2, `cần ít nhất 2 dòng chờ xác minh để phép đo có nghĩa, thấy ${JSON.stringify(confirmable)}`);
  assert.equal(await bulk.clicks(), 0, 'chưa bấm gì trước khi đo');

  await page.getByTestId('criterion-confirm-visible').click();
  await page.getByTestId('criterion-confirm-all-dialog').waitFor({ timeout: 5000 });
  assert.equal(await bulk.clicks(), 1, 'mở danh sách xem trước là một cú bấm');
  const listed = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid^="criterion-confirm-all-item-"]'))
    .map(item => item.getAttribute('data-testid').replace('criterion-confirm-all-item-', '')));
  assert.deepEqual(
    [...listed].sort(),
    [...confirmable].sort(),
    `danh sách xem trước phải đúng những dòng sẽ ghi, thấy ${JSON.stringify(listed)} so với ${JSON.stringify(confirmable)}`,
  );
  assert.equal(posts.length, 0, 'chưa được ghi gì trước khi HR bấm xác nhận');

  await page.getByTestId('criterion-confirm-all-submit').click();
  await page.getByTestId('criterion-confirm-all-done').waitFor({ timeout: 20000 });
  assert.equal(await bulk.clicks(), 2, 'một hành động cho mọi số dòng = hai cú bấm');
  assert.equal(posts.length, confirmable.length, `phải có đúng một POST cho mỗi dòng, thấy ${JSON.stringify(posts)}`);
  const bulkResultIds = posts.map(entry => entry.resultId);
  assert.equal(
    new Set(bulkResultIds).size,
    bulkResultIds.length,
    `không được ghi hai lần cho cùng một kết quả, thấy ${JSON.stringify(bulkResultIds)} cho ${JSON.stringify(confirmable)}`,
  );
  confirmable.forEach(id => assert.ok(bulkResultIds.includes(`${id}:r-c2`), `thiếu review của ${id}: ${JSON.stringify(bulkResultIds)}`));
  assert.ok(posts.every(entry => entry.decision === 'CONFIRMED'), 'tất cả phải là xác nhận, không có đánh dấu sai');
  for (const id of confirmable) {
    assert.match(await page.getByTestId(`criterion-reviewed-${id}`).innerText(), /Đã xác nhận/, `dòng ${id} phải hiện đã xác nhận`);
  }
  // Hộp thoại đóng bằng transition của MUI, nên chờ nó rời DOM thay vì đọc
  // ngay (đọc ngay sẽ thấy nó còn đó vài trăm ms).
  await page.getByTestId('criterion-confirm-all-dialog').waitFor({ state: 'detached', timeout: 5000 });
  assert.equal(
    await page.getByTestId('criterion-confirm-visible').isDisabled(),
    true,
    'hết dòng chờ thì nút xác nhận tất cả phải tắt, không mời bấm lại',
  );
  const bulkClicks = await bulk.clicks();

  // --- 2. Đối chứng: từng dòng một như trước --------------------------------
  const oneByOne = await openScreen(browser);
  assert.deepEqual(
    [...oneByOne.confirmable].sort(),
    [...confirmable].sort(),
    'hai nhánh phải cùng một tập dòng, nếu không thì so sánh vô nghĩa',
  );
  for (const id of oneByOne.confirmable) {
    await oneByOne.page.getByTestId(`criterion-confirm-${id}`).click();
    await oneByOne.page.getByTestId(`criterion-reviewed-${id}`).waitFor({ timeout: 15000 });
  }
  const oneByOneClicks = await oneByOne.clicks();
  assert.equal(oneByOneClicks, oneByOne.confirmable.length, 'từng dòng một tốn đúng một cú bấm mỗi dòng');
  assert.equal(oneByOne.posts.length, oneByOne.confirmable.length, 'từng dòng một cũng một POST mỗi dòng');
  assert.ok(
    bulkClicks < oneByOneClicks,
    `một hành động phải ít cú bấm hơn từng dòng một: ${bulkClicks} so với ${oneByOneClicks}`,
  );

  // --- 3. Bấm đúp nút xác nhận: không ghi gấp đôi ---------------------------
  const double = await openScreen(browser);
  await double.page.getByTestId('criterion-confirm-visible').click();
  await double.page.getByTestId('criterion-confirm-all-submit').waitFor({ timeout: 5000 });
  await double.page.evaluate(() => {
    const button = document.querySelector('[data-testid="criterion-confirm-all-submit"]');
    if (!button) throw Error('không thấy nút xác nhận tất cả');
    button.click();
    button.click();
  });
  await double.page.getByTestId('criterion-confirm-all-done').waitFor({ timeout: 20000 });
  await double.page.waitForTimeout(400);
  assert.equal(
    double.posts.length,
    double.confirmable.length,
    `bấm đúp không được ghi gấp đôi: ${double.posts.length} POST cho ${double.confirmable.length} dòng`,
  );

  console.log(`CONFIRM_ALL ${JSON.stringify({
    rows: confirmable.length,
    bulkClicks,
    bulkPosts: posts.length,
    oneByOneClicks,
    oneByOnePosts: oneByOne.posts.length,
    doubleClickPosts: double.posts.length,
    confirmable,
  })}`);

  for (const arm of [bulk, oneByOne, double]) {
    assert.deepEqual(arm.unexpected, [], `không có request lạ: ${arm.unexpected.join(', ')}`);
    await arm.context.close();
  }
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
