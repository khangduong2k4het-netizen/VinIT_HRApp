/**
 * Đo Dashboard như một danh sách việc, không phải một bảng số liệu.
 *
 * Câu hỏi cần trả lời được bằng số: HR mở Dashboard buổi sáng, có thấy ngay
 * "hôm nay làm gì" và bấm tới đúng chỗ trong bao nhiêu thao tác không?
 *
 *   node tests/dashboard-metrics.cjs > metrics.json
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

  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  await page.waitForSelector('text=Việc cần làm').catch(() => {});

  report.layout = await page.evaluate(() => {
    const top = el => (el ? Math.round(el.getBoundingClientRect().top + window.scrollY) : null);
    const h = el => (el ? Math.round(el.getBoundingClientRect().height) : null);
    const byText = text => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,div')]
      .find(el => el.children.length === 0 && (el.textContent || '').trim() === text);
    const kpiCards = [...document.querySelectorAll('a[aria-label]')].filter(a => /^[^:]+:/.test(a.getAttribute('aria-label') || ''));
    return {
      fold: window.innerHeight,
      pageHeight: document.documentElement.scrollHeight,
      kpiCount: kpiCards.length,
      kpiHeight: kpiCards[0] ? h(kpiCards[0]) : null,
      kpiOffsetPx: top(kpiCards[0]),
      workQueueHeadingOffsetPx: top(byText('Việc cần làm')),
      workQueueItemCount: document.querySelectorAll('[data-testid="work-queue-item"], a[data-testid^="work-queue-"]').length,
      actionableAboveFold: [...document.querySelectorAll('a[href*="queue="], a[href*="tab="]')]
        .filter(a => a.getBoundingClientRect().top < window.innerHeight).length,
      horizontalScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    };
  });

  // What can HR actually press in the first screen, and does it lead to work?
  report.firstScreen = await page.evaluate(() => {
    const inFold = el => {
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= window.innerHeight && r.width > 0;
    };
    const links = [...document.querySelectorAll('a[href]')].filter(inFold).map(a => ({
      label: (a.getAttribute('aria-label') || a.textContent || '').trim().slice(0, 60),
      href: a.getAttribute('href'),
    }));
    return {
      links: links.slice(0, 12),
      linksWithQueueTarget: links.filter(l => /queue=|tab=/.test(l.href || '')).length,
      linksToBarePositionList: links.filter(l => (l.href || '') === '/positions').length,
    };
  });

  // Every work-queue item must point somewhere that filters, not at a bare list.
  report.queueTargets = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('a[href]').forEach(a => {
      const label = (a.getAttribute('aria-label') || a.textContent || '').trim();
      if (/hồ sơ|Kiểm tra file|Xác minh|Cảnh báo trùng|Chưa đánh giá|miss-match/i.test(label)) {
        out.push({ label: label.slice(0, 50), href: a.getAttribute('href') });
      }
    });
    return out.slice(0, 10);
  });

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
