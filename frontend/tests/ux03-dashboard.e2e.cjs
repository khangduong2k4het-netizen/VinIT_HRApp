/**
 * UX-03 — Dashboard phải dẫn tới việc, và trạng thái lọc phải nhìn thấy được.
 *
 * Bốn điều được kiểm, mỗi điều từng là một lỗi thật:
 *  1. Mọi nút trong "Việc cần làm" trỏ tới danh sách ĐÃ LỌC theo hàng đợi, không
 *     phải danh sách trơn. Deep link trơn là "deep link giả": HR bấm "Xác minh hồ sơ"
 *     rồi thấy cả 12 hồ sơ, không biết hồ sơ nào cần mình.
 *  2. Khi không có scorecard nào đến hạn (trường hợp bình thường), khối đó không
 *     được chiếm một tiêu đề + hai dòng giải thích trước hàng đợi việc.
 *  3. Việc HR đã kiểm xong phải hiện thành số, để "cần xác minh" giảm đi vì đã làm
 *     chứ không phải vì dữ liệu biến mất.
 *  4. Chip lọc ở /positions phải cho thấy chip nào đang chọn. Trước đây
 *     /positions?status=CLOSED hiện "0/1 vị trí" dưới bốn chip trông y hệt nhau.
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
    localStorage.setItem('hra_access_token', 'dashboard');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#work-queue');

  // --- 1. Every work-queue action filters, none opens a bare list -----------
  const targets = await page.evaluate(() => [...document.querySelectorAll('#work-queue a[href]')]
    .map(a => ({ label: (a.textContent || '').trim().slice(0, 40), href: a.getAttribute('href') })));
  assert.ok(targets.length >= 3, `expected a real queue, got ${JSON.stringify(targets)}`);
  const bare = targets.filter(t => /\/applicants$/.test(t.href || ''));
  assert.deepEqual(bare, [], `these actions open an unfiltered list: ${JSON.stringify(bare)}`);
  const filtered = targets.filter(t => /queue=[A-Z_]+/.test(t.href || ''));
  assert.ok(filtered.length >= 3, 'queue actions carry the queue code');

  // And the code is one the ranking page actually understands.
  const known = ['ALL', 'SHORTLIST', 'FILE_REVIEW', 'DUPLICATE', 'NEEDS_VERIFICATION', 'POSSIBLE_MISMATCH', 'NOT_ASSESSED', 'MEETS_MANDATORY'];
  filtered.forEach(t => {
    const code = new URL(t.href, 'http://x').searchParams.get('queue');
    assert.ok(known.includes(code), `unknown queue code "${code}" in ${t.href}`);
  });

  // --- 2. An empty scorecard block must not outrank real work ---------------
  const scorecardHeading = await page.getByText('Nhắc hạn scorecard', { exact: true }).count();
  const emptyNote = await page.getByText('Không có scorecard quá hạn hoặc đến hạn trong 24 giờ.').count();
  assert.equal(emptyNote, 1, 'the empty state still says the truth');
  assert.equal(scorecardHeading, 0, 'but it no longer spends a heading and a caveat on "nothing due"');

  const workHeadingTop = await page.evaluate(() => {
    const el = [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === 'Việc cần làm');
    return el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null;
  });
  assert.ok(workHeadingTop !== null && workHeadingTop <= 380, `the work queue must start high, got ${workHeadingTop}px`);

  // --- 3. Finished verification work is visible, not a shrinking number -----
  await page.getByTestId('verification-complete-summary').waitFor();
  assert.match(await page.getByTestId('verification-complete-summary').innerText(), /Đã xác minh xong 3 hồ sơ/);

  // --- 4. The selected filter chip is visibly selected ----------------------
  await page.goto(`${base}/positions?status=CLOSED`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(400);
  const chips = await page.evaluate(() => {
    const group = document.querySelector('[role="group"][aria-label="Lọc vị trí"]');
    return [...(group?.querySelectorAll('.MuiChip-root') || [])].filter(c => /^(Tất cả|Đang mở|Tạm dừng|Đã đóng) /.test(c.textContent.trim()))
      .map(c => ({
        label: c.textContent.trim(),
        pressed: c.getAttribute('aria-pressed'),
        outlined: /MuiChip-outlined/.test(c.className),
        visible: c.getBoundingClientRect().width > 0,
      }));
  });
  assert.equal(chips.length, 4, `expected four status chips, got ${JSON.stringify(chips)}`);
  const closed = chips.find(c => c.label.startsWith('Đã đóng'));
  const all = chips.find(c => c.label.startsWith('Tất cả'));
  assert.equal(closed.pressed, 'true', 'the closed filter is the pressed one');
  // Outlined-vs-filled is what a sighted user actually sees; aria-pressed only
  // helps a screen reader. Checking only the aria attribute is how this shipped
  // looking identical in the first place.
  assert.equal(closed.outlined, false, 'the selected chip is filled');
  assert.equal(all.outlined, true, 'the others stay outlined');

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
  console.log('UX-03 dashboard: every queue action filters, empty scorecard collapsed, finished verification counted, selected filter visible: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
