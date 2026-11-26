/**
 * Vòng xác minh không bắt HR bấm thừa.
 *
 * Ba thứ được khoá ở đây, vì mỗi thứ hỏng đi là một thao tác thừa quay lại:
 *  1. Xác nhận xong con trỏ sang tiêu chí còn chờ kế tiếp — kể cả khi HR đã chọn
 *     tiêu chí bằng j/k, trước đây con trỏ đứng lại ở tiêu chí vừa xong và lần
 *     bấm `1` sau đó không làm gì (đo được 7 lần bấm vô ích cho 2 tiêu chí).
 *  2. Không tải lại cả hồ sơ sau mỗi lần xác nhận: tiến độ đổi ngay tại chỗ và
 *     không có request GET nào chen vào.
 *  3. CV đang mở thì đi theo tiêu chí, và hồ sơ kế tiếp được tải trước.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const activeCriterion = page => page.evaluate(() => {
  const card = document.querySelector('[data-testid="evidence-card"][data-active="true"]');
  return card ? card.id.replace(/^criterion-/, '') : null;
});

// Trang của khung CV, đọc đúng dòng "Trang N" cạnh tiêu đề "CV gốc": trong thẻ
// bằng chứng cũng có "Trang 2" của trích dẫn, đọc cả trang sẽ ra nhầm số.
const cvPage = page => page.evaluate(() => {
  const src = document.querySelector('#cv-pdf-viewer')?.getAttribute('src') || '';
  const fromHash = src.match(/#page=(\d+)/);
  if (fromHash) return Number(fromHash[1]);
  const heading = [...document.querySelectorAll('h4')].find(el => el.textContent.trim() === 'CV gốc');
  const fromHeader = (heading?.parentElement?.textContent || '').match(/Trang (\d+)/);
  return fromHeader ? Number(fromHeader[1]) : null;
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

  const openProfile = async () => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'auto-advance');
      localStorage.setItem('hra_locale', 'vi');
    });
    const unexpected = await installMockApi(context);
    const page = await context.newPage();
    const calls = [];
    page.on('request', request => {
      const url = new URL(request.url());
      calls.push({ method: request.method(), path: url.pathname, rsc: Boolean(request.headers()['next-router-prefetch']) });
    });
    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');
    await page.waitForTimeout(300);
    return { context, page, calls, unexpected };
  };

  // --- 1. Đã chọn tiêu chí bằng j: xác nhận xong tự sang còn chờ ----------
  {
    const { context, page, calls, unexpected } = await openProfile();
    assert.equal(await activeCriterion(page), 'c2', 'con trỏ bắt đầu ở tiêu chí chờ đầu tiên');
    await page.keyboard.press('j');
    assert.equal(await activeCriterion(page), 'c3', 'j chọn tiêu chí kế');

    const before = calls.length;
    await page.keyboard.press('1');
    await page.waitForFunction(() => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });
    assert.equal(await activeCriterion(page), 'c2', 'xác nhận c3 xong con trỏ sang tiêu chí còn chờ duy nhất (c2), không đứng lại');

    // Lần bấm kế tiếp phải có tác dụng ngay: không cần j/k nào nữa.
    await page.keyboard.press('1');
    await page.waitForFunction(() => /Đã xác minh đủ 2\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });

    const during = calls.slice(before);
    // Hồ sơ (GET /applications/{id}) và lịch sử trạng thái là thứ loadData() tải
    // lại; hai request đó phải biến mất. Panel profile và ghi chú là component
    // riêng, vẫn tự gọi khi props đổi — đo riêng, không tính là tải lại hồ sơ.
    assert.deepEqual(
      during.filter(call => call.method === 'GET' && /^\/v1\/applications\/app-2(\/status-events)?$/.test(call.path)).map(call => call.path),
      [],
      'mỗi lần xác nhận không kéo theo tải lại hồ sơ và lịch sử trạng thái',
    );
    assert.equal(during.filter(call => call.method === 'POST').length, 2, 'chỉ hai lần ghi nhận xác minh');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  // --- 2. CV đang mở: nó đi theo tiêu chí vừa nhảy tới --------------------
  {
    const { context, page, unexpected } = await openProfile();
    assert.equal(await cvPage(page), 1, 'CV chưa mở thì chưa tải và đứng ở trang đầu');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(900);
    assert.equal(await cvPage(page), 3, 'Enter mở đúng trang trích dẫn của tiêu chí đang chọn');
    await page.keyboard.press('1');
    await page.waitForFunction(() => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });
    assert.equal(await activeCriterion(page), 'c3');
    assert.equal(await cvPage(page), 4, 'khung CV chuyển sang trang của tiêu chí kế tiếp');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  // --- 3. Bấm 1 liên tiếp là đủ cho cả hồ sơ ------------------------------
  {
    const { context, page, unexpected } = await openProfile();
    await page.keyboard.press('1');
    await page.waitForTimeout(500);
    assert.equal(await progress(page), '1/2');
    assert.equal(await activeCriterion(page), 'c3', 'không cần phím nào khác để tới tiêu chí kế');
    await page.keyboard.press('1');
    await page.waitForTimeout(500);
    assert.equal(await progress(page), '2/2');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  // --- 4. Hồ sơ kế tiếp được tải trước khi HR bấm n -----------------------
  {
    const { context, page, calls, unexpected } = await openProfile();
    const prefetched = calls.filter(call => call.path === '/positions/p1/applicants/app-8');
    assert.ok(prefetched.length >= 1, 'route của hồ sơ kế tiếp được tải trước, không đợi tới lúc bấm n');
    if (!(await page.getByTestId('review-shortcuts').count())) throw Error('shortcut hint missing');
    await page.keyboard.press('n');
    await page.waitForFunction(() => /Ngô Thanh Tùng/.test(document.body.innerText), undefined, { timeout: 15000 });
    assert.equal(new URL(page.url()).searchParams.get('queue'), 'NEEDS_VERIFICATION', 'queue context survives the hop');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  console.log('Review loop: confirm advances the cursor and the CV, no full reload, next profile prefetched: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
