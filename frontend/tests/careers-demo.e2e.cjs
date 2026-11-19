// Browser acceptance for explicitly isolated synthetic demo only; creates demo applications.
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const base = process.env.CAREERS_DEMO_E2E_BASE;
const health = process.env.CAREERS_DEMO_E2E_HEALTH;
if (process.env.CAREERS_DEMO_E2E !== '1' || !base || !health ||
    ![base, health].every(v => ['localhost', '127.0.0.1', '[::1]'].includes(new URL(v).hostname))) {
  throw Error('Requires explicit local, disposable synthetic demo confirmation.');
}
(async () => {
  const check = await fetch(health); assert.equal((await check.json()).environment, 'testing');
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '/tmp/chromium', args: ['--no-sandbox'], headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '/demo');
    await page.getByText('Demo tuyển dụng — dữ liệu tổng hợp').waitFor();
    const cv = await (await page.request.get(base + '/v1/demo/fixture/cv')).body();
    const email = await (await page.request.get(base + '/v1/demo/fixture/email')).body();
    await page.getByRole('link', { name: '1. Trang ứng tuyển giả' }).click();
    const source = page.locator('.MuiCard-root').filter({ hasText: 'DEMO-IT-001' });
    await source.getByRole('button', { name: 'Ứng tuyển demo' }).click();
    await page.locator('input[name=name]').fill('Ứng viên giả Browser');
    await page.locator('input[name=email]').fill('browser@example.invalid');
    await page.locator('input[name=cv]').setInputFiles({ name: 'cv-gia.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: cv });
    await page.getByRole('checkbox', { name: /Talent Pool DEMO/ }).check();
    await page.getByRole('button', { name: 'Gửi hồ sơ demo' }).click();
    await page.getByText('Đã nhận hồ sơ tổng hợp', { exact: false }).waitFor();
    const token = await page.locator('code').innerText(); assert.match(token, /^[a-f0-9]{64}$/);
    console.log('Careers form + synthetic CV + opt-in: OK');
    await page.goto(base + '/demo');
    await page.getByRole('button', { name: '2–3. Mở workspace HR demo' }).click();
    await page.getByText('Talent Pool — DEMO').waitFor();
    const src = '8fab8c45-b683-469f-8d82-52714390715a';
    const dst = '607b5006-bc44-4820-a9f2-9192eb7e7084';
    await page.waitForFunction(async ([s, d]) => {
      const token = localStorage.getItem('hra_access_token');
      const response = await fetch(`/v1/careers-demo/pool/scan?source_position_id=${s}&target_position_id=${d}`, { headers: { Authorization: `Bearer ${token}` } });
      return response.ok && (await response.json()).items.some(item => item.display_name === 'Ứng viên giả Browser');
    }, [src, dst], { timeout: 45000, polling: 1500 });
    await page.getByRole('combobox', { name: 'Vị trí nguồn' }).click();
    await page.getByRole('option', { name: /DEMO-IT-001/ }).click();
    await page.getByRole('combobox', { name: 'Vị trí đích có rubric duyệt' }).click();
    await page.getByRole('option', { name: /DEMO-IT-002/ }).click();
    await page.getByRole('button', { name: 'Kiểm tra pool demo' }).click();
    await page.getByText('Ứng viên giả Browser', { exact: false }).waitFor();
    await page.getByText('Nguyễn Văn An', { exact: false }).waitFor();
    console.log('Worker + Talent Pool HR demo: OK');
    await page.goto(base + '/careers-demo');
    await page.getByLabel('Mã demo').fill(token);
    await page.getByRole('button', { name: 'Rút lựa chọn' }).click();
    await page.getByText('Nếu mã demo hợp lệ, lựa chọn đã được rút.').waitFor();
    await page.goto(base + '/talent-pool-demo');
    await page.getByRole('combobox', { name: 'Vị trí nguồn' }).click();
    await page.getByRole('option', { name: /DEMO-IT-001/ }).click();
    await page.getByRole('combobox', { name: 'Vị trí đích có rubric duyệt' }).click();
    await page.getByRole('option', { name: /DEMO-IT-002/ }).click();
    await page.getByRole('button', { name: 'Kiểm tra pool demo' }).click();
    await page.getByText('Nguyễn Văn An', { exact: false }).waitFor();
    assert.equal(await page.getByText('Ứng viên giả Browser', { exact: false }).count(), 0);
    console.log('Consent withdrawal prevents later demo scan: OK');
    await page.goto(base + '/email-demo');
    await page.locator('input[type=file]').setInputFiles({ name: 'email-gia.eml', mimeType: 'message/rfc822', buffer: email });
    await page.getByRole('button', { name: 'Tiếp nhận demo' }).click();
    await page.getByText('Đã tiếp nhận email giả vào hàng đợi xử lý CV demo.').waitFor();
    const res = await page.evaluate(async id => {
      const token = localStorage.getItem('hra_access_token');
      const response = await fetch(`/v1/applications?position_id=${id}`, { headers: { Authorization: `Bearer ${token}` } });
      return response.ok ? response.json() : [];
    }, src);
    assert.ok(res.some(item => item.source_code === 'EMAIL_DEMO'));
    console.log('Offline synthetic email upload -> HR applications: OK');
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
