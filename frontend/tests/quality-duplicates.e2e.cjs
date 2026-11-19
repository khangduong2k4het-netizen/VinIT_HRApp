/* Run only against a disposable local database with the documented synthetic fixture. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright-core');

const base = process.env.HRA_E2E_BASE_URL;
const health = process.env.HRA_E2E_HEALTH_URL;
const fixture = process.env.HRA_E2E_FIXTURE;
if (process.env.HRA_E2E_SYNTHETIC !== '1' || !base || !health || !fixture) {
  throw new Error('Set synthetic opt-in, local base/health URLs and synthetic fixture path.');
}
for (const value of [base, health]) {
  if (!['127.0.0.1','localhost','[::1]'].includes(new URL(value).hostname)) throw new Error('Local URLs only.');
}
const f = JSON.parse(fs.readFileSync(fixture, 'utf8'));

(async () => {
  const response = await fetch(health);
  assert.equal((await response.json()).environment, 'testing');
  const browser = await chromium.launch({ headless: true, executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE });
  const errors = [];
  try {
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.evaluate(token => localStorage.setItem('hra_access_token', token), f.lead_token);
    await page.goto(base + '/quality');
    await page.getByText('Synthetic QA Candidate', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Mở kiểm định', exact: true }).first().click();
    await page.getByText('Synthetic Python engineer experience', { exact: true }).first().waitFor();
    await page.locator('iframe').waitFor();
    await page.waitForFunction(() => document.querySelector('iframe')?.src.startsWith('blob:'));
    await page.getByRole('button', { name: 'Nhận kiểm định', exact: true }).click();
    await page.getByLabel('Kết luận kiểm định').click();
    await page.getByRole('option', { name: 'Có lỗi cần xử lý', exact: true }).click();
    await page.getByRole('button', { name: 'Thêm phản hồi lỗi', exact: true }).click();
    await page.getByLabel('Mô tả lỗi và đề nghị xử lý').fill('Synthetic evidence issue for engineering review');
    await page.getByRole('button', { name: 'Nộp kết quả kiểm định', exact: true }).click();
    await page.getByText('Phản hồi đã ghi nhận', { exact: true }).waitFor();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Tải phản hồi cho đội kỹ thuật', exact: true }).click();
    const download = await downloadPromise;
    const report = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(report.verdict, 'ISSUES_FOUND');
    assert.equal(report.flags.length, 1);
    assert.equal('candidate_name' in report, false);
    await page.getByRole('button', { name: 'English', exact: true }).click();
    await page.getByRole('heading', { name: 'Quality inspection', exact: true }).waitFor();
    assert.equal(await page.getByText('Synthetic evidence issue for engineering review', { exact: false }).count() > 0, true);
    console.log('HR Lead inspection, source/text/evidence, submission, feedback export and bilingual UI: PASS');

    const hrContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const hr = await hrContext.newPage();
    hr.on('pageerror', e => errors.push(e.message));
    await hr.goto(base);
    await hr.evaluate(token => localStorage.setItem('hra_access_token', token), f.hr_token);
    await hr.goto(`${base}/positions/${f.position}/applicants/${f.application}`);
    await hr.getByText('Hồ sơ trùng giữa các vị trí', { exact: true }).waitFor();
    await hr.getByText('Có hồ sơ nghi trùng ở vị trí ngoài phạm vi của bạn.', { exact: false }).waitFor();
    assert.equal((await hr.locator('body').innerText()).includes('Restricted Other Position'), false);
    await hr.getByRole('button', { name: 'Quét lại', exact: true }).click();
    await hr.getByText('Có hồ sơ nghi trùng ở vị trí ngoài phạm vi của bạn.', { exact: false }).waitFor();
    assert.equal(await hr.getByRole('link', { name: 'Kiểm định chất lượng', exact: true }).count(), 0);
    await hr.goto(base + '/quality');
    await hr.getByText('Chỉ HR Lead có quyền kiểm định', { exact: true }).waitFor();
    assert.equal(await hr.getByRole('button', { name: 'Mở kiểm định', exact: true }).count(), 0);
    assert.deepEqual(errors, []);
    console.log('HR duplicate warning, restricted-position privacy and QA access denial: PASS');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
