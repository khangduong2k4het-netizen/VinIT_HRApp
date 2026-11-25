/**
 * Đo độ trễ chip "N ghi chú riêng tư" trên trang hồ sơ.
 *
 * Câu hỏi: cửa sổ dừng 600 ms (nạp ghi chú khi HR ở lại hồ sơ) có đáng không, hay
 * chip hiện ra muộn tới mức không ai kịp dùng? Đo từ lúc nội dung hồ sơ hiện ra
 * (`verification-progress`) tới lúc chip có mặt, hai lần ở hai hồ sơ, trên CPU bình
 * thường và khi CPU bị bóp chậm 6 lần (CDP `Emulation.setCPUThrottlingRate`).
 *
 * Chip chỉ hiện khi đã có ghi chú (`notes.length > 0`), nên mock trả sẵn ghi chú
 * cho hai hồ sơ. Không assert: đây là phép đo, in một dòng `CHIP {json}` để so
 * giữa các bản build (cửa sổ dừng 600 ms / 250 ms / không cửa sổ).
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/notes-chip-latency.cjs
 */
const { chromium } = require('playwright-core');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

// Chip hiện ngay khi có dữ liệu; 3 giây là quá đủ cho cả bản chậm nhất, và tránh
// treo lâu khi bản đang đo không bao giờ hiện chip (không cửa sổ, chỉ tải khi mở).
const CHIP_TIMEOUT_MS = 3_000;
const PROFILE_TIMEOUT_MS = 20_000;

const makeNote = id => ({
  note_id: id,
  content: `Ghi chú ${id}`,
  criterion_id: null,
  created_at: '2026-11-20T09:00:00Z',
  author_name: 'Nguyễn Thu Hằng',
});

const noteRoute = id => route => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify([makeNote(`${id}-n1`), makeNote(`${id}-n2`)]),
});

const measureMode = async (browser, label, cpuRate) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', `chip-${Math.random().toString(36).slice(2)}`);
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context, {
    '/v1/applications/app-5/private-notes': noteRoute('app-5'),
    '/v1/applications/app-0/private-notes': noteRoute('app-0'),
  });
  const page = await context.newPage();
  // Bóp CPU trước khi trang chạy: cần đo cả chi phí dựng trang, không chỉ request.
  const cdp = await context.newCDPSession(page);
  if (cpuRate !== 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpuRate });

  const notesRequests = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/private-notes')) notesRequests.push({ path, at: Date.now() });
  });

  const samples = [];
  // Mốc "vừa bấm vào hồ sơ": dùng để biết chính bản thân hồ sơ hiện ra mất bao lâu
  // (cần biết CPU bị bóp có thật sự chậm hơn không).
  let markAt = Date.now();
  const measureProfile = async () => {
    // Hồ sơ hiện ra = khung xác minh đã dựng (h1 + badge trạng thái đã có).
    await page.getByTestId('verification-progress').waitFor({ timeout: PROFILE_TIMEOUT_MS });
    const shownAt = Date.now();
    const profileReadyMs = shownAt - markAt;
    const chip = await page.getByTestId('hr-note-count').first()
      .waitFor({ timeout: CHIP_TIMEOUT_MS })
      .then(() => Date.now() - shownAt)
      .catch(() => null);
    const askAt = notesRequests.length ? notesRequests[notesRequests.length - 1].at - shownAt : null;
    samples.push({
      profileReadyMs,
      showedChipMs: chip,
      notesAskedAfterShowMs: askAt,
      chipText: chip === null ? null : (await page.getByTestId('hr-note-count').first().innerText()).trim(),
    });
  };

  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor({ timeout: PROFILE_TIMEOUT_MS });
  markAt = Date.now();
  await page.locator('table tbody tr a[href*="/applicants/app-5"]').first().click();
  await measureProfile();
  // Hồ sơ kế: đo lần hai để thấy số ổn định hay dao động. Chờ tên trên tiêu đề
  // đổi, nếu không "hồ sơ hiện ra" sẽ tính từ lúc trang cũ còn trên màn hình.
  const nameBefore = (await page.locator('h1').innerText()).trim();
  markAt = Date.now();
  await page.keyboard.press('n');
  await page.waitForFunction(name => {
    const heading = document.querySelector('h1');
    return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== name);
  }, nameBefore, { timeout: PROFILE_TIMEOUT_MS });
  await measureProfile();

  await context.close();
  return { label, cpuRate, samples, notesRequests: notesRequests.length, unexpected: unexpected.length };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const results = [];
  for (const [label, cpuRate] of [['1x', 1], ['6x', 6]]) {
    results.push(await measureMode(browser, label, cpuRate));
  }
  console.log(`CHIP ${JSON.stringify(results)}`);
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
