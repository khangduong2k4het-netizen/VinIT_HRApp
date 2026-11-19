/**
 * DOCX CV preview inside the application profile.
 *
 * A .docx cannot be rendered by the browser, and converting it on the server
 * would add a converter to the request path. Instead the file HR already fetched
 * (on demand, never on open) is read in the page: the ZIP is inflated and the
 * WordprocessingML text becomes paragraphs. This test serves real .docx bytes
 * built in the fixture and checks:
 *  1. Nothing is fetched when the profile opens.
 *  2. After asking, the DOCX text is readable in-app with no PDF iframe.
 *  3. The page stepper stays disabled (a .docx has no pages here), and the text
 *     is rendered as text, not as raw bytes or markup.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi, DOCX_PARAGRAPHS } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'docx-preview');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));

  const cvRequests = [];
  page.on('request', request => { if (/cv-file/.test(request.url())) cvRequests.push(request.url()); });

  await page.goto(`${base}/positions/p1/applicants/app-docx`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="evidence-card"]');

  // --- 1. Still nothing fetched until HR asks ------------------------------
  await page.waitForTimeout(500);
  assert.deepEqual(cvRequests, [], 'opening a profile must not download the CV');
  assert.equal(await page.getByTestId('docx-text').count(), 0, 'no preview before the file is asked for');

  // --- 2. Ask for the CV: DOCX text, not a download ------------------------
  await page.getByRole('button', { name: 'Xem CV gốc' }).click();
  await page.waitForSelector('[data-testid="docx-text"]');
  assert.equal(cvRequests.length, 1, `expected exactly one CV request, got ${cvRequests.length}`);
  assert.equal(await page.locator('#cv-pdf-viewer').count(), 0, 'a DOCX must not be fed to the PDF viewer');

  const text = await page.getByTestId('docx-text').innerText();
  for (const paragraph of DOCX_PARAGRAPHS.filter(Boolean)) {
    const expected = paragraph.replace(/\s+/g, ' ').trim();
    assert.ok(text.replace(/\s+/g, ' ').includes(expected), `DOCX text must be readable: ${expected}`);
  }
  const headingParagraph = page.getByTestId('docx-text').getByRole('paragraph').first();
  assert.equal((await headingParagraph.innerText()).trim(), DOCX_PARAGRAPHS[0], 'the first Word paragraph is the first paragraph shown');
  assert.equal(await page.getByTestId('docx-text').locator('w\\:p').count(), 0, 'raw document XML must not leak into the DOM');
  assert.match(text, /Tải CV gốc để xem đúng định dạng/, 'HR is told the original layout may differ');

  // --- 3. No pagination for a flattened document ---------------------------
  assert.equal(await page.getByRole('button', { name: 'Trang sau' }).isDisabled(), true);

  assert.deepEqual(pageErrors, [], `no client-side exceptions: ${pageErrors.join(' | ')}`);
  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  console.log('DOCX preview: fetched only on ask, text readable in-app, no PDF viewer, original layout disclaimer kept: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
