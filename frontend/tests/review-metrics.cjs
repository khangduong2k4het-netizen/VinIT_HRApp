/**
 * Đo màn Candidate Review: HR đọc bằng chứng và đối chiếu tiêu chí ở đâu trong
 * màn hình, tốn bao nhiêu thao tác, và có phải cuộn ngang không.
 *
 *   node tests/review-metrics.cjs   -> JSON ra stdout
 */
const { chromium } = require('playwright-core');
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
    localStorage.setItem('hra_access_token', 'metrics');
    localStorage.setItem('hra_locale', 'vi');
  });
  await installMockApi(context);
  const page = await context.newPage();
  const report = { viewport: { width: 1440, height: 900 } };

  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Kết quả đánh giá theo tiêu chí');

  report.layout = await page.evaluate(() => {
    const top = el => el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null;
    const h = el => el ? Math.round(el.getBoundingClientRect().height) : null;
    const byText = text => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,div,p,span')]
      .find(el => el.children.length === 0 && (el.textContent || '').trim() === text);
    const firstCriterion = document.querySelector('.evidence-card');
    const cards = [...document.querySelectorAll('.evidence-card')];
    const cvButton = [...document.querySelectorAll('button')].find(b => /CV/.test(b.textContent || ''));
    return {
      fold: window.innerHeight,
      pageHeight: document.documentElement.scrollHeight,
      h1Count: document.querySelectorAll('h1').length,
      nameOffsetPx: top(document.querySelector('h1')),
      firstCriterionOffsetPx: top(firstCriterion),
      criterionRows: cards.length,
      criterionCardHeights: cards.slice(0, 4).map(h),
      quotesShown: [...document.querySelectorAll('.evidence-card')].filter(c => c.querySelector('p[style*="italic"], .MuiTypography-root[style*="italic"]')).length,
      unverifiedCitations: [...document.querySelectorAll('.evidence-card')].filter(c => /Trích dẫn chưa xác minh/.test(c.textContent || '')).length,
      unclearRows: [...document.querySelectorAll('.evidence-card')].filter(c => /Chưa rõ|chưa đủ bằng chứng|Không tìm thấy bằng chứng/.test(c.textContent || '')).length,
      criteriaHeadingOffsetPx: top(byText('Kết quả đánh giá theo tiêu chí')),
      cvActionOffsetPx: top(cvButton),
      horizontalScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  });

  // How many clicks to answer "which criterion is missing evidence, and where?"
  report.evidenceSteps = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.evidence-card')];
    const insufficient = rows.filter(r => /chưa đủ bằng chứng|insufficient/i.test(r.textContent || ''));
    return {
      rowsWithInsufficientMarkedInline: insufficient.length,
      totalRows: rows.length,
      // A row that states its own verdict means no extra click is needed.
      rowsNeedingAClickToRevealVerdict: rows.filter(r => !/Đáp ứng|Chưa đủ|Chưa đánh giá|Không đáp ứng/.test(r.textContent || '')).length,
    };
  });

  // --- U2: the rubric is on the page, and opening it must not cost height -----
  report.requirement = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('[data-testid="evidence-card"]')];
    const toggles = [...document.querySelectorAll('[data-testid="criterion-requirement-toggle"]')];
    return {
      cards: cards.length,
      cardsWithRequirement: cards.filter(c => c.querySelector('[data-testid="criterion-requirement-toggle"]')).length,
      allCollapsed: toggles.every(t => t.getAttribute('aria-expanded') === 'false'),
      pageHeightWithClosed: document.documentElement.scrollHeight,
    };
  });
  if (report.requirement.cardsWithRequirement > 0) {
    const first = page.locator('[data-testid="criterion-requirement-toggle"]').first();
    await first.click();
    await page.waitForTimeout(350);
    report.requirement.afterOpen = await page.evaluate(() => ({
      expanded: document.querySelector('[data-testid="criterion-requirement-toggle"]').getAttribute('aria-expanded'),
      pageHeightWithOneOpen: document.documentElement.scrollHeight,
      text: document.querySelector('[id^="requirement-"]')?.innerText.slice(0, 80) || '',
    }));
  }

  // --- U3: no CV request until a citation is pressed --------------------------
  const cvCalls = [];
  page.on('request', r => { if (r.url().includes('cv-file')) cvCalls.push(r.url()); });
  report.citation = await page.evaluate(() => {
    const quote = document.querySelector('[data-testid="citation-quote"]');
    return {
      present: !!quote,
      isButton: quote?.getAttribute('role') === 'button',
      label: quote?.getAttribute('aria-label') || null,
    };
  });
  report.citation.cvRequestsBeforeClick = cvCalls.length;
  if (report.citation.present && report.citation.isButton) {
    await page.locator('[data-testid="citation-quote"]').first().click();
    await page.waitForTimeout(900);
    report.citation.cvRequestsAfterClick = cvCalls.length;
    report.citation.selectedPageChip = await page.locator('[data-testid="citation-status-VERIFIED"], [data-testid="citation-status-FAILED"], [data-testid="citation-status-PENDING"]').first().innerText().catch(() => null);
  }

  // --- U4: skip link and citation states -------------------------------------
  await page.goto(`${base}/positions/p1/applicants/app-2`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');
  await page.keyboard.press('Tab');
  report.keyboard = await page.evaluate(() => ({
    firstStop: document.activeElement?.textContent?.trim() || document.activeElement?.getAttribute('aria-label'),
    firstStopVisible: (() => { const r = document.activeElement?.getBoundingClientRect(); return r ? r.top >= 0 : false; })(),
  }));
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  report.keyboard.afterSkip = await page.evaluate(() => ({
    focusId: document.activeElement?.id,
    focusTag: document.activeElement?.tagName,
  }));
  report.keyboard.tabsFromContent = 0;
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press('Tab');
    report.keyboard[`afterTabsFromContent${i + 1}`] = await page.evaluate(() => document.activeElement?.textContent?.trim().slice(0, 28) || document.activeElement?.getAttribute('aria-label'));
  }
  report.citationStates = await page.evaluate(() => {
    const out = {};
    document.querySelectorAll('[data-testid^="citation-status-"]').forEach(el => {
      const key = el.getAttribute('data-testid').replace('citation-status-', '');
      out[key] = el.textContent.trim();
    });
    return out;
  });

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
