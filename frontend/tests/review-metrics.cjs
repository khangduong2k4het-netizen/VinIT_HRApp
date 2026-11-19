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

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
