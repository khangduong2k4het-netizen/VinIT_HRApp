const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use a local disposable Next.js server.');
}

// UX-R6: the ranking screen must reach its data sooner without losing any filter
// behaviour. Measured at 1440x900, the viewport the report argues from.
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await c.addInitScript(() => { localStorage.setItem('hra_access_token', 'r6'); localStorage.setItem('hra_locale', 'vi'); });
  const unexpected = await installMockApi(c);
  const page = await c.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();

  const box = await page.evaluate(() => {
    const top = el => el.getBoundingClientRect().top + window.scrollY;
    const rows = [...document.querySelectorAll('table tbody tr')];
    return {
      fold: window.innerHeight,
      firstRowTop: Math.round(top(rows[0])),
      rowsVisibleInFirstScreen: rows.filter(r => top(r) < window.innerHeight).length,
    };
  });
  assert.equal(box.fold, 900);
  assert.ok(box.firstRowTop <= 660, `first data row must sit well inside the fold, got ${box.firstRowTop}px`);
  assert.ok(box.rowsVisibleInFirstScreen >= 2, `at least two rows must be visible, got ${box.rowsVisibleInFirstScreen}`);

  // --- R6-a: one primary action, the rest behind an explicit menu -------------
  assert.equal(await page.getByRole('button', { name: 'Chạy đánh giá & xếp hạng' }).count(), 1);
  assert.equal(await page.getByRole('button', { name: 'Làm mới', exact: true }).count(), 0, 'refresh is no longer a third competing button');
  await page.getByRole('button', { name: /Hành động khác/ }).click();
  assert.equal(await page.getByRole('menuitem', { name: 'Làm mới' }).isVisible(), true);
  assert.equal(await page.getByRole('menuitem', { name: 'Chia sẻ Shortlist' }).isVisible(), true);
  await page.keyboard.press('Escape');

  // --- Discoverability of the hidden actions --------------------------------
  // A bare "⋮" does not tell HR that refresh and share live behind it, so the
  // trigger must name them: in the tooltip for sighted users, in aria-label for
  // screen readers.
  assert.equal(
    await page.getByRole('button', { name: /^Làm mới$/ }).count(),
    0,
    'no anonymous "refresh" button left in the header',
  );
  assert.equal(
    await page.getByRole('button', { name: 'Hành động khác: Làm mới, Chia sẻ Shortlist' }).count(),
    1,
  );
  await page.getByRole('button', { name: 'Hành động khác: Làm mới, Chia sẻ Shortlist' }).hover();
  assert.equal(await page.getByRole('tooltip').filter({ hasText: 'Làm mới và Chia sẻ Shortlist' }).isVisible(), true, 'hovering explains what the menu holds');
  await page.mouse.move(0, 0);

  // --- R6-b: the explanation still exists, word for word, one click away -----
  const toggle = page.getByTestId('how-to-read-toggle');
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
  assert.equal(await page.locator('#how-to-read-applicants').count(), 0, 'collapsed by default');
  await toggle.click();
  const explanation = await page.locator('#how-to-read-applicants').innerText();
  assert.match(explanation, /điểm một phần chỉ tính trên phần trọng số đã có bằng chứng/);
  assert.match(explanation, /chưa phải điểm cuối/);
  assert.match(explanation, /Mở rộng từng dòng để xem kết quả theo từng tiêu chí/);
  await toggle.click();
  // Collapse unmounts on exit, but only after its animation: wait for that
  // instead of counting instantly and racing the transition.
  await page.locator('#how-to-read-applicants').waitFor({ state: 'detached' });
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false');

  // Keyboard only: the toggle must be reachable, open with the keyboard, and
  // report its state, because it is the only way to reach the business rules.
  await page.getByTestId('how-to-read-toggle').focus();
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('data-testid')), 'how-to-read-toggle');
  await page.keyboard.press('Enter');
  assert.equal(await toggle.getAttribute('aria-expanded'), 'true', 'Enter opens it');
  await page.locator('#how-to-read-applicants').waitFor();
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('data-testid')), 'how-to-read-toggle', 'focus stays on the toggle so the next Tab continues sensibly');
  await page.keyboard.press('Enter');
  await page.locator('#how-to-read-applicants').waitFor({ state: 'detached' });

  // The sort explanation is a visible caption, not a tooltip: a new user must be
  // able to read it without discovering anything.
  const explanationLine = page.getByTestId('sort-explanation');
  assert.equal(await explanationLine.isVisible(), true);
  // Mặc định là chế độ Xếp hạng; câu giải thích phải đổi theo chế độ đang chọn.
  assert.match(await explanationLine.innerText(), /Sắp theo thứ hạng của lần chạy gần nhất/);
  // Chế độ xem đã gộp vào ô Sắp xếp (trước là hai nút riêng trùng lựa chọn):
  // đổi chế độ ghi lại URL, nên chờ đúng trạng thái thay vì bấm liền tay.
  assert.equal(await page.getByRole('button', { name: 'Cần rà soát', exact: true }).count(), 0,
    'the mode is chosen once, in the sort select');
  const sortSelect = page.getByRole('combobox', { name: 'Sắp xếp danh sách' });
  await sortSelect.click();
  await page.getByRole('option', { name: 'Ưu tiên rà soát' }).click();
  await page.waitForFunction(() => decodeURIComponent(location.search).includes('sort=REVIEW_PRIORITY'));
  await page.getByTestId('sort-explanation').waitFor();
  assert.match(await page.getByTestId('sort-explanation').innerText(), /không phải thứ tự xếp hạng/);
  await sortSelect.click();
  await page.getByRole('option', { name: 'Thứ hạng' }).click();
  await page.waitForFunction(() => !decodeURIComponent(location.search).includes('sort=REVIEW_PRIORITY'));
  // It must not be an alert box anymore (that is what cost 48px of height).
  assert.equal(await explanationLine.evaluate(el => (el.closest('[role="alert"]') !== null)), false);
  assert.equal(await page.getByRole('alert').filter({ hasText: 'không phải thứ tự xếp hạng' }).count(), 0);

  // --- Filter bar: one row of controls, no duplicated buttons ----------------
  const bar = page.getByTestId('applicant-filter-bar');
  assert.equal(await bar.count(), 1, 'search, owner, sort and evidence filters sit in one bar');
  assert.equal(await page.getByTestId('owner-select').count(), 1, 'owner filter is one select, not a row of chips');
  assert.equal(await page.getByTestId('owner-chip-ALL').count(), 0);

  // --- Duyệt liên tiếp: hồ sơ kế tiếp mở ngay từ đầu trang ------------------
  const nextProfile = page.getByTestId('open-next-profile');
  assert.equal(await nextProfile.isVisible(), true, 'the next profile is reachable without scrolling to the table');
  const nextHref = await nextProfile.getAttribute('href');
  assert.match(nextHref, /^\/positions\/p1\/applicants\/app-\d+/, 'it links straight into the first profile that still needs work');

  // --- R6-c: every filter that used to be a card still works -----------------
  // The four summary cards are gone; each of their behaviours must survive.
  assert.equal(await page.getByTestId('applicant-funnel').innerText().then(t => /\/\d+ hồ sơ đã có trong xếp hạng/.test(t)), true, 'file counts stay visible as one line');
  // MUI renders a clickable Chip as a div with role=button whose accessible name
  // is the aria-label, so match on the visible text of the chip element itself.
  const chip = label => page.locator('[data-testid="queue-chip-counts"]').getByRole('button', { name: new RegExp(label) });
  assert.equal(await chip('Cần xác minh').count(), 1, 'verification filter survives as a chip');
  assert.equal(await chip('Cảnh báo trùng').count(), 1, 'duplicate filter survives as a chip');
  assert.equal(await chip('Đã shortlist').count(), 1, 'shortlist filter survives as a chip');
  assert.equal(await chip('Tất cả').count(), 1, 'the unfiltered queue survives');

  for (const [label, queueCode] of [
    ['Cần xác minh', 'NEEDS_VERIFICATION'],
    ['Cảnh báo trùng', 'DUPLICATE'],
    ['Đã shortlist', 'SHORTLIST'],
  ]) {
    await chip(label).click();
    await page.waitForFunction(code => decodeURIComponent(location.search).includes(`queue=${code}`), queueCode);
    await chip('Tất cả').click();
    await page.waitForFunction(code => !decodeURIComponent(location.search).includes(`queue=${code}`), queueCode);
  }

  if (errors.length) throw Error(errors.join('\n'));
  if (unexpected.length) throw Error(`Unexpected requests:\n${unexpected.join('\n')}`);
  await c.close();
  await browser.close();
  console.log(`Ranking compact: first row at ${box.firstRowTop}px with ${box.rowsVisibleInFirstScreen} rows in the first screen, one primary action, explanation preserved, all four filter behaviours kept: OK`);
})().catch(e => { console.error(e); process.exit(1); });
