/**
 * Capture the three HR screens the UI/UX review is about, plus one "after"
 * frame of the header that UX-R4 proposes to tighten.
 *
 *   HRA_E2E_BASE_URL=http://localhost:3015 \
 *   HRA_E2E_CHROMIUM_EXECUTABLE=/tmp/chromium \
 *   HRA_E2E_CHROMIUM_ARGS='["--no-sandbox"]' \
 *   node tests/ui-screenshots.cjs [outputDir]
 *
 * Output: doc/ui-review/*.png (full page, 1440px wide, Vietnamese locale).
 */
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}
const outDir = path.resolve(process.argv[2] || path.join(__dirname, '..', '..', 'doc', 'ui-review'));
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'screenshot');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);

  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(e.message));

  const shoot = async (name, urlPath, waitFor) => {
    await page.goto(`${base}${urlPath}`, { waitUntil: 'networkidle' });
    if (waitFor) await page.waitForSelector(waitFor, { timeout: 15000 });
    await page.waitForTimeout(600);
    const file = path.join(outDir, `${name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    const { width, height } = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    console.log(`saved ${path.relative(process.cwd(), file)} (${width}x${height})`);
  };

  await shoot('01-dashboard', '/dashboard', 'text=Việc cần làm');
  await shoot('02-applicant-ranking', '/positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY', 'table');
  await shoot('03-candidate-review', '/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY', 'text=Kết quả đánh giá theo tiêu chí');

  await browser.close();
  if (unexpected.length) console.log('UNMOCKED:', [...new Set(unexpected)].join(' | '));
  if (pageErrors.length) console.log('PAGE ERRORS:', [...new Set(pageErrors)].join(' | '));
})().catch(err => { console.error(err); process.exit(1); });
