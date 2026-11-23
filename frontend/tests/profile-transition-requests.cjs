/**
 * Đo số request mỗi lần chuyển hồ sơ trên trang hồ sơ (bấm `n` / "Hồ sơ tiếp theo").
 *
 * Câu hỏi: chuyển sang hồ sơ kế trong **cùng một vị trí** thì có cần gọi lại
 * `GET /v1/criteria/position/{id}/approved` không? Rubric không đổi giữa các lần
 * bấm, nên nếu lần chuyển nào cũng gọi lại thì đó là request thừa lặp đi lặp lại
 * trong cả vòng duyệt.
 *
 * Script: mở danh sách → mở hồ sơ đầu tiên → bấm `n` ba lần, mỗi lần đếm `GET`
 * vào `/v1/`, tách riêng rubric / chi tiết hồ sơ / `auth/me` / các path khác.
 * Cửa sổ đếm chỉ mở trong lúc chuyển, không tính request của lần mở đầu tiên.
 *
 * `auth/me`: mỗi lần bấm `n` từng hỏi hai lần (khung trang kiểm tra lại quyền
 * khi `pathname` đổi + trang hồ sơ tự hỏi mình là ai sau mỗi lần được gắn lại),
 * hai request cách nhau 40–60 ms cho cùng một câu trả lời. Từ khi có
 * `lib/meCache.ts`, cả hai dùng chung một bản trong 30 giây.
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/profile-transition-requests.cjs
 * In một dòng `TRANSITIONS {json}`.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const TRANSITIONS = 3;
const RUBRIC_PATH = '/v1/criteria/position/p1/approved';

const profileName = page => page.evaluate(() => {
  const heading = document.querySelector('h1');
  return heading ? heading.textContent.trim() : null;
});

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'transition-requests');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();
  const requests = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/v1/') && request.method() === 'GET') requests.push(url.pathname);
  });

  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();
  await page.locator('table tbody tr a[href*="/applicants/app-"]').first().click();
  await page.getByTestId('verification-progress').waitFor();
  await page.locator('[data-testid="evidence-card"]').first().waitFor();
  await page.waitForLoadState('networkidle');
  // Rubric của lần mở đầu tiên không tính vào phép đo chuyển hồ sơ.
  await page.waitForTimeout(400);

  const transitions = [];
  for (let index = 0; index < TRANSITIONS; index += 1) {
    const from = await profileName(page);
    const startedAt = requests.length;
    await page.keyboard.press('n');
    await page.waitForFunction(name => {
      const heading = document.querySelector('h1');
      return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== name);
    }, from, { timeout: 15000 });
    await page.getByTestId('verification-progress').waitFor();
    await page.locator('[data-testid="evidence-card"]').first().waitFor();
    // Chờ cả các request phụ (chi tiết hồ sơ kế, tải trước) xong mới chốt số.
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(400);

    const during = requests.slice(startedAt);
    transitions.push({
      from,
      to: await profileName(page),
      totalGet: during.length,
      rubric: during.filter(path => path === RUBRIC_PATH).length,
      auth: during.filter(path => path === '/v1/auth/me').length,
      detail: during.filter(path => /^\/v1\/applications\/app-\d+$/.test(path)).length,
      paths: during.reduce((acc, path) => ({ ...acc, [path]: (acc[path] || 0) + 1 }), {}),
    });
  }

  assert.deepEqual(unexpected, [], `không có request lạ: ${unexpected.join(', ')}`);

  // Dùng lại rubric chỉ có nghĩa nếu nội dung rubric vẫn tới màn hình: mở
  // "Yêu cầu gốc" ở thẻ đầu tiên và đọc câu mô tả lấy từ
  // `GET /criteria/position/p1/approved`. Không có bước này thì một cache trả về
  // rỗng cũng làm số request đẹp mà màn hình mất thông tin.
  await page.getByRole('button', { name: 'Yêu cầu gốc' }).first().click();
  await page
    .getByText(/Xây dựng và vận hành dịch vụ Python chạy thật|Thiết kế schema quan hệ và tối ưu truy vấn/)
    .first()
    .waitFor({ timeout: 5000 });

  // Lần chuyển đầu có thể cần rubric; các lần sau trong cùng vị trí thì không.
  // Nếu cache rubric không hoạt động, mọi lần chuyển đều có đúng 1 request.
  const rubricPerTransition = transitions.map(transition => transition.rubric);
  console.log(`TRANSITIONS ${JSON.stringify({
    transitions,
    rubricPerTransition,
    authPerTransition: transitions.map(transition => transition.auth),
    totalGetPerTransition: transitions.map(transition => transition.totalGet),
    fullLoopGetRequests: transitions.reduce((sum, transition) => sum + transition.totalGet, 0),
  })}`);

  const cached = rubricPerTransition.slice(1).every(count => count === 0);
  assert.ok(cached, `rubric phải được dùng lại giữa các lần chuyển, thấy ${JSON.stringify(rubricPerTransition)}`);

  // Danh tính cũng dùng chung: tối đa một lần hỏi `auth/me` cho mỗi lần chuyển
  // (0 khi bản dùng chung còn hiệu lực, 1 khi đã quá 30 giây). Hai lần là lỗi
  // cũ quay lại.
  const authPerTransition = transitions.map(transition => transition.auth);
  assert.ok(
    authPerTransition.every(count => count <= 1),
    `mỗi lần chuyển chỉ được hỏi auth/me tối đa một lần, thấy ${JSON.stringify(authPerTransition)}`,
  );
  // Chốt chặn cho phép kiểm trên: số request đẹp không được vì danh tính không
  // bao giờ được tải. Menu tài khoản phải hiện đúng tên lấy từ `auth/me`.
  await page.getByRole('button', { name: 'Mở menu tài khoản' }).click();
  await page.getByText('Nguyễn Thu Hằng').first().waitFor({ timeout: 5000 });
  await page.keyboard.press('Escape');

  await page.close();
  await context.close();
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
