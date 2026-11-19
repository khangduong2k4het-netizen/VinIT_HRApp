/**
 * Measure the screen-level facts the UI/UX backlog argues from, instead of
 * eyeballing them: how many controls compete above the fold, how far the
 * primary action sits, and whether prev/next survives a deep link.
 *
 *   HRA_E2E_BASE_URL=http://localhost:3015 \
 *   HRA_E2E_CHROMIUM_EXECUTABLE=/tmp/chromium \
 *   HRA_E2E_CHROMIUM_ARGS='["--no-sandbox"]' \
 *   node tests/ui-ux-metrics.cjs
 *
 * Prints a JSON report on stdout. Read-only: no navigation changes values.
 */
const { chromium } = require('playwright-core');
const { installMockApi, visible, workQueueSummary } = require('./fixtures/hr-screens.cjs');

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
    localStorage.setItem('hra_access_token', 'metrics');
    localStorage.setItem('hra_locale', 'vi');
  });
  await installMockApi(context);
  const page = await context.newPage();
  const report = {};

  // ---- Dashboard -----------------------------------------------------------
  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Việc cần làm');
  report.dashboard = await page.evaluate(() => {
    const fold = window.innerHeight;
    const top = el => el.getBoundingClientRect().top + window.scrollY;
    const queue = document.querySelector('#work-queue');
    const queueItems = [...document.querySelectorAll('#work-queue [class*="MuiCard-root"]')]
      .filter(card => card.querySelector('button, a'));
    const buttons = [...document.querySelectorAll('#work-queue button, #work-queue a')];
    return {
      viewportHeight: fold,
      pageHeight: document.documentElement.scrollHeight,
      scrollsToReachQueue: Math.round(top(queue) / fold * 100) / 100,
      queueItemCards: queueItems.length,
      queueActionButtons: buttons.length,
      // Distinct numeric figures rendered above the work queue: the four KPI
      // cards. Each one is a promise the reviewer has to reconcile by hand.
      kpiCards: [...document.querySelectorAll('main a[aria-label]')].length,
      kpiValuesAboveQueue: [...document.querySelectorAll('a[aria-label] h3')].map(n => n.textContent?.trim()),
    };
  });

  // ---- Applicant ranking ---------------------------------------------------
  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.waitForSelector('table');
  report.ranking = await page.evaluate(() => {
    const fold = window.innerHeight;
    const top = el => el.getBoundingClientRect().top + window.scrollY;
    const chips = [...document.querySelectorAll('[role="group"] button, .MuiChip-root')];
    const queueChips = chips.filter(c => /\d+/.test(c.textContent || ''));
    const rows = [...document.querySelectorAll('tbody tr')];
    const headerTop = top(document.querySelector('thead'));
    const firstRow = rows[0];
    return {
      viewportHeight: fold,
      pageHeight: document.documentElement.scrollHeight,
      scrollPages: Math.round(document.documentElement.scrollHeight / fold * 100) / 100,
      filterControlsAboveTable: document.querySelectorAll('thead ~ * button, [role="group"] button').length,
      chipsWithCounts: queueChips.length,
      chipLabels: queueChips.map(c => (c.textContent || '').trim().replace(/\s+/g, ' ')),
      tableHeaderOffsetPx: Math.round(headerTop),
      firstRowOffsetPx: firstRow ? Math.round(top(firstRow)) : null,
      // Reading "why this person is in this group" requires either expanding a
      // row or opening the profile: the list itself shows only a group label.
      rowsWithInlineReason: rows.filter(r => /Không tìm thấy bằng chứng|Dấu hiệu|chưa đáp ứng|Cần HR/i.test(r.textContent || '')).length,
      totalRows: rows.length,
      tableMaxHeight: getComputedStyle(document.querySelector('.MuiTableContainer-root')).maxHeight,
      stickyHeader: Boolean(document.querySelector('thead th')) && getComputedStyle(document.querySelector('thead th')).position === 'sticky',
    };
  });

  // ---- Candidate review, reached from the list (sessionStorage present) ----
  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.waitForSelector('table');
  // The mobile card copy of the link is hidden at md+, so click the table one.
  await page.locator('tbody a[href*="/applicants/app-2"]').first().click();
  await page.waitForSelector('text=Kết quả đánh giá theo tiêu chí');
  report.candidateFromList = await page.evaluate(() => {
    // An enabled prev/next is an <a> (Link); a disabled one is a <button>.
    // Counting only buttons made a working control look absent.
    const nav = [...document.querySelectorAll('a, button')]
      .filter(el => /^(Hồ sơ trước|Hồ sơ tiếp theo)$/.test((el.textContent || '').trim()));
    const body = document.body.innerText;
    const title = document.querySelector('h1');
    const y = el => (el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null);
    const byText = (sel, re) => [...document.querySelectorAll(sel)].find(el => re.test(el.textContent || ''));
    const headings = [...document.querySelectorAll('h1')].map(el => el.textContent.trim());
    return {
      prevNextEnabled: nav.filter(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true').length,
      prevNextTotal: nav.length,
      counterText: (body.match(/Hồ sơ \d+\/\d+ trong hàng đợi/) || [null])[0],
      hiddenPageHeight: document.documentElement.scrollHeight,
      viewportHeight: window.innerHeight,
      h1: title ? title.textContent.trim() : null,
      /** UX-R4: how much of the first screen is spent before the verdict. */
      h1OffsetPx: y(title),
      verdictStripOffsetPx: y(byText('h3, p, span', /^Điểm trên tiêu chí đã có bằng chứng$/)),
      scoreOffsetPx: y(byText('h3, p', /^69%$/)),
      criteriaHeaderOffsetPx: y(byText('h4, h3, p', /^Kết quả đánh giá theo tiêu chí$/)),
      h1Count: headings.length,
      nameRepeatedInFirstScreen: headings.filter(h => (body.indexOf(h) !== -1) && h).length >= 1
        ? [...document.querySelectorAll('h1, [class*="MuiTypography-root"]')]
            .filter(el => y(el) !== null && y(el) < 260 && (el.textContent || '').trim() === (title ? title.textContent.trim() : '\u0000')).length
        : 0,
      // The CV is deliberately lazy now (UX P1-4): it must NOT be fetched
      // just because the profile opened. Recorded so the report can't claim
      // otherwise by accident.
      cvRequestedOnOpen: /CV gốc chưa được tải/.test(body),
    };
  });

  // ---- Candidate review, opened as a deep link (no sessionStorage) ---------
  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Kết quả đánh giá theo tiêu chí');
  report.candidateDeepLink = await page.evaluate(() => {
    const nav = [...document.querySelectorAll('a, button')]
      .filter(el => /^(Hồ sơ trước|Hồ sơ tiếp theo)$/.test((el.textContent || '').trim()));
    return {
      prevNextEnabled: nav.filter(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true').length,
      prevNextTotal: nav.length,
      counterText: (document.body.innerText.match(/Hồ sơ \d+\/\d+ trong hàng đợi/) || [null])[0],
    };
  });

  // ---- Cross-screen consistency -------------------------------------------
  report.consistency = {
    // What the dashboard promises vs. what the ranking chip answers.
    dashboardNeedsVerification: workQueueSummary.applications_needing_verification,
    rankingQueueSizeFromMock: visible.filter(item => item.matching_status !== 'NOT_ASSESSED'
      && (item.matching_status === 'NEEDS_HR_VERIFICATION' || item.evidence_coverage < 0.7)).length,
  };
  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  report.consistency.pageCaption = (await page.getByTestId('applicant-count').innerText()).trim();
  report.consistency.chipNeedsVerification = (await page.evaluate(() =>
    [...document.querySelectorAll('.MuiChip-root')]
      .map(c => (c.textContent || '').trim())
      .find(t => t.startsWith('Cần xác minh')))) || null;

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
