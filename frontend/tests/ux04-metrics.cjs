/**
 * UX-04 — khi HR đối chiếu bằng chứng, CV gốc có còn trong tầm mắt không?
 *
 * Việc đối chiếu là "đọc câu trích dẫn ở tiêu chí N, mở CV trang M, so". Nếu
 * khung CV cuộn đi mất khi HR xuống tiêu chí thứ ba thì mỗi lần đối chiếu là một
 * lần cuộn lên xuống — đúng cái đắt nhất của màn hình này.
 *
 *   node tests/ux04-metrics.cjs > ux04.json
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
    localStorage.setItem('hra_access_token', 'ux04');
    localStorage.setItem('hra_locale', 'vi');
  });
  await installMockApi(context);
  const page = await context.newPage();
  await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  const report = { viewport: { width: 1440, height: 900 } };

  // Where each evidence card sits, and is the CV panel on screen next to it?
  report.cards = await page.evaluate(() => {
    function findCvPanel() {
      const leaf = [...document.querySelectorAll('*')].find(el => el.children.length === 0 && /^CV gốc$/.test((el.textContent || '').trim()));
      return leaf ? (leaf.closest('.MuiPaper-root') || leaf.parentElement) : null;
    }

    const cards = [...document.querySelectorAll('[data-testid="evidence-card"]')];
    const panel = findCvPanel();
    return cards.map((card, i) => {
      const r = card.getBoundingClientRect();
      return { index: i + 1, top: Math.round(r.top + scrollY), height: Math.round(r.height), cvPanelTop: panel ? Math.round(panel.getBoundingClientRect().top + scrollY) : null };
    });
  });

  // Scroll so the last criterion is on screen; is the CV still visible beside it?
  report.lastCriterionCheck = await page.evaluate(() => {
    function findCvPanel() {
      const leaf = [...document.querySelectorAll('*')].find(el => el.children.length === 0 && /^CV gốc$/.test((el.textContent || '').trim()));
      return leaf ? (leaf.closest('.MuiPaper-root') || leaf.parentElement) : null;
    }

    const cards = [...document.querySelectorAll('[data-testid="evidence-card"]')];
    const last = cards[cards.length - 1];
    if (!last) return null;
    last.scrollIntoView({ block: 'center' });
    const label = findCvPanel()?.querySelector('h2,h3,div');
    const panel = findCvPanel();
    const r = panel?.getBoundingClientRect();
    const onScreen = !!r && r.bottom > 0 && r.top < window.innerHeight;
    return {
      scrollY: Math.round(window.scrollY),
      cvPanelTop: r ? Math.round(r.top) : null,
      cvPanelBottom: r ? Math.round(r.bottom) : null,
      cvPanelVisible: onScreen,
      cvPanelHeight: r ? Math.round(r.height) : null,
      cvPanelWidthPx: r ? Math.round(r.width) : null,
      emptyRightColumnPx: r ? Math.max(0, Math.round(window.innerHeight - Math.max(0, r.bottom))) : null,
      cvHeadingVisible: !!label && label.getBoundingClientRect().top >= 0 && label.getBoundingClientRect().bottom <= window.innerHeight,
    };
  });

  // Does opening a profile fetch the CV file before HR asks for it?
  const requests = [];
  page.on('request', r => { if (/cv-file/.test(r.url())) requests.push(r.url()); });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');
  await page.waitForTimeout(800);
  report.cvRequestsOnOpen = requests.length;

  console.log(JSON.stringify(report, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
