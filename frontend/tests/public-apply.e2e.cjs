// Invoked by backend/tests/test_public_intake_browser.py with an isolated Next
// server, migrated disposable DB, real API, and synthetic DOCX files. No API mocks.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright-core');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw new Error('A disposable local Next.js server is required. Use the backend browser test harness.');
}
const fixture = JSON.parse(fs.readFileSync(process.env.HRA_E2E_FIXTURE, 'utf8'));

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: process.env.HRA_E2E_CHROMIUM_ARGS ? JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS) : [],
    headless: true,
  });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    const errors = [];
    const submissions = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/v1/public/')) {
        assert.equal(request.headers().authorization, undefined, 'Public requests must not attach an HR token');
      }
    });
    page.on('response', response => {
      if (response.request().method() === 'POST' && response.url().endsWith('/apply')) submissions.push(response.status());
    });
    const openForm = async () => {
      await page.goto(base + '/apply');
      await page.getByRole('button', { name: 'Ứng tuyển', exact: true }).click();
      assert.equal(await page.getByRole('checkbox').count(), 1);
      assert.equal(await page.getByRole('checkbox').nth(0).isChecked(), false);
    };

    await openForm();
    await page.getByRole('button', { name: 'Gửi hồ sơ', exact: true }).click();
    await page.getByText('Vui lòng chọn tệp CV.', { exact: true }).waitFor();
    await page.locator('input[type=file]').setInputFiles(fixture.first_cv);
    await page.getByRole('button', { name: 'Gửi hồ sơ', exact: true }).click();
    await page.getByText('Cần đồng ý cho phép sử dụng thông tin hồ sơ để ứng tuyển.', { exact: true }).waitFor();
    assert.equal(submissions.length, 0);
    await page.getByRole('checkbox').nth(0).check();
    await page.getByRole('button', { name: 'Gửi hồ sơ', exact: true }).click();
    await page.getByText('Đã nhận hồ sơ của bạn.', { exact: true }).waitFor();
    assert.match(await page.locator('code').innerText(), /^[0-9a-f]{64}$/);

    await openForm();
    await page.locator('input[type=file]').setInputFiles(fixture.second_cv);
    await page.getByRole('checkbox').nth(0).check();
    await page.getByRole('button', { name: 'Gửi hồ sơ', exact: true }).click();
    await page.getByText('Đã nhận hồ sơ của bạn.', { exact: true }).waitFor();
    const token = await page.locator('code').innerText();
    assert.match(token, /^[0-9a-f]{64}$/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.getByRole('link', { name: '/apply/withdraw', exact: true }).click();
    await page.getByRole('textbox', { name: 'Mã rút lại đồng ý', exact: true }).fill('bad');
    await page.getByRole('button', { name: 'Rút lại đồng ý', exact: true }).click();
    await page.getByText('Mã gồm 64 ký tự (0-9, a-f).', { exact: true }).waitFor();
    await page.getByRole('textbox', { name: 'Mã rút lại đồng ý', exact: true }).fill(token);
    await page.getByRole('button', { name: 'Rút lại đồng ý', exact: true }).click();
    await page.getByText('Nếu mã hợp lệ, lựa chọn Talent Pool đã được rút.', { exact: true }).waitFor();
    assert.deepEqual(submissions, [202, 202]);
    assert.deepEqual(errors, []);
    console.log('Public portal browser flow passed: single combined consent, mobile receipt, withdrawal.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
