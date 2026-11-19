/**
 * UX-04 — CV gốc phải ở lại trong tầm mắt khi HR đối chiếu bằng chứng.
 *
 * Việc thật của màn hình này là "đọc câu trích dẫn ở tiêu chí N, mở CV trang M,
 * so". Trước khi sửa, ở tiêu chí cuối khung CV nằm 637px phía trên màn hình
 * trong khi cột phải còn 900px trống — mỗi tiêu chí là một lần cuộn lên rồi cuộn
 * xuống. Hàng rào này khoá cả ba nguyên nhân đã từng làm hỏng nó:
 *
 *  1. `html, body { overflow-x: hidden }` biến body thành scroll container và
 *     vô hiệu hoá MỌI position: sticky trong app (phải là `clip`).
 *  2. Cột CV phải sticky từ md trở lên; và không được thấp hơn thanh điều hướng
 *     (header 64px + thanh hàng đợi tới ~143px), nếu không tiêu đề "CV gốc" bị che.
 *  3. Trang hồ sơ vẫn KHÔNG được tự tải CV khi mở (đó là quyền riêng, có audit).
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const VIEWPORT = { width: 1440, height: 900 };
const BAR_BOTTOM = 143; // fixed header 64 + sticky queue bar (76 + 67)

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: VIEWPORT });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'ux04');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const cvRequests = [];
  page.on('request', r => { if (/cv-file/.test(r.url())) cvRequests.push(r.url()); });

  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 0. Nothing is fetched until HR asks ---------------------------------
  await page.waitForTimeout(500);
  assert.deepEqual(cvRequests, [], 'opening a profile must not download the CV');

  // --- 1. Sticky is actually effective (the body must not scroll-trap it) --
  const scrolled = await page.evaluate(() => {
    const heading = [...document.querySelectorAll('h4')].find(el => /CV gốc/.test(el.textContent || ''));
    const item = heading.closest('.MuiGrid-item');
    const cards = [...document.querySelectorAll('[data-testid="evidence-card"]')];
    const last = cards[cards.length - 1];
    last.scrollIntoView({ block: 'center' });
    return {
      y: Math.round(heading.getBoundingClientRect().top),
      itemTop: Math.round(item.getBoundingClientRect().top),
      bodyOverflowX: getComputedStyle(document.body).overflowX,
      scrollY: Math.round(window.scrollY),
      lastCardVisible: last.getBoundingClientRect().top < window.innerHeight && last.getBoundingClientRect().bottom > 0,
    };
  });
  assert.equal(scrolled.bodyOverflowX, 'clip', 'overflow-x must not be hidden: it silently disables every sticky element');
  assert.ok(scrolled.lastCardVisible, 'the last criterion is the one being compared');
  // The heading must be on screen AND clear of the sticky queue bar. Checking only
  // "top > 0" is how a version shipped with the title tucked under the bar: the
  // element was technically visible, just covered.
  assert.ok(scrolled.y > 0 && scrolled.y < VIEWPORT.height,
    `CV heading must stay on screen while reviewing, got ${scrolled.y}px`);
  assert.ok(scrolled.y >= BAR_BOTTOM,
    `the CV heading must clear the sticky queue bar (${BAR_BOTTOM}px), got ${scrolled.y}px`);

  // --- 2. Asking for it loads it, once ------------------------------------
  await page.getByRole('button', { name: 'Xem CV gốc' }).click();
  await page.waitForTimeout(600);
  assert.equal(cvRequests.length, 1, `expected exactly one CV request after asking, got ${cvRequests.length}`);

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  console.log(`UX-04 sticky CV: viewer stays on screen beside the last criterion (${scrolled.y}px), nothing fetched until asked: OK`);
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
