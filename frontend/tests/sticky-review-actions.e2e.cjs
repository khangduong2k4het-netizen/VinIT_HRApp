/**
 * Thanh dính trên hồ sơ phải trả lời được hai câu ngay tại chỗ, không cần cuộn:
 * còn bao nhiêu tiêu chí chờ, và quyết định cho tiêu chí đang chọn là gì.
 *
 * Trước đây cả hai nằm trong thẻ bằng chứng: HR đọc CV ở cột phải, thẻ đang xem
 * đã trôi khỏi màn hình (trên điện thoại càng rõ), muốn xác nhận phải cuộn
 * ngược lên đúng thẻ.
 *
 * Kiểm ở cả 390px và 1440px, vì đây là thay đổi dành cho màn hẹp.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const progressText = page => page.evaluate(() => {
  const chip = document.querySelector('[data-testid="verification-progress"]');
  const match = (chip?.textContent || '').match(/Đã xác minh (?:đủ )?(\d+)\/(\d+)/);
  return match ? `${match[1]}/${match[2]}` : null;
});

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  for (const viewport of [{ width: 390, height: 844, label: '390' }, { width: 1440, height: 900, label: '1440' }]) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'sticky');
      localStorage.setItem('hra_locale', 'vi');
    });
    const unexpected = await installMockApi(context);
    const page = await context.newPage();
    const reviewPosts = [];
    page.on('request', request => {
      if (/\/review$/.test(new URL(request.url()).pathname) && request.method() === 'POST') reviewPosts.push(1);
    });

    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');
    await page.waitForTimeout(300);

    // --- Còn bao nhiêu tiêu chí chờ, ngay trên thanh dính -------------------
    assert.equal((await page.getByTestId('sticky-pending').innerText()).trim(), 'Còn 2/2 tiêu chí chờ', `${viewport.label}: pending count`);

    // --- Hai nút nằm trong khung nhìn, không phải cuộn ---------------------
    for (const testId of ['sticky-confirm', 'sticky-reject']) {
      const button = page.getByTestId(testId);
      assert.equal(await button.isVisible(), true, `${viewport.label}: ${testId} visible`);
      const box = await button.boundingBox();
      assert.ok(box, `${viewport.label}: ${testId} has a box`);
      assert.ok(box.y >= 0 && box.y + box.height <= viewport.height, `${viewport.label}: ${testId} is on screen (y=${Math.round(box.y)})`);
      assert.ok(box.x >= 0 && box.x + box.width <= viewport.width, `${viewport.label}: ${testId} is inside the width`);
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, `${viewport.label}: no horizontal overflow`);

    // --- Xác nhận từ thanh dính: ghi nhận và chuyển tiêu chí ---------------
    assert.equal(await page.getByTestId('sticky-confirm').isDisabled(), false, `${viewport.label}: active criterion can be confirmed`);
    await page.getByTestId('sticky-confirm').click();
    await page.waitForFunction(() => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });
    assert.equal((await page.getByTestId('sticky-pending').innerText()).trim(), 'Còn 1/2 tiêu chí chờ');
    assert.equal(await progressText(page), '1/2');
    assert.equal(reviewPosts.length, 1, `${viewport.label}: one recorded review`);

    // --- Đánh dấu sai từ thanh dính: mở đúng hộp thoại lý do ---------------
    assert.equal(await page.getByTestId('sticky-reject').isDisabled(), false);
    await page.getByTestId('sticky-reject').click();
    await page.getByTestId('reject-confirm').waitFor({ timeout: 5000 });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    assert.equal(await page.getByTestId('reject-confirm').count(), 0, `${viewport.label}: dialog closes without recording anything`);
    assert.equal(reviewPosts.length, 1, `${viewport.label}: closing the reject dialog records nothing`);

    // --- Hết việc thì thanh dính nói đủ, và không còn gì để bấm ------------
    await page.getByTestId('sticky-confirm').click();
    await page.waitForFunction(() => /Đã xác minh đủ 2\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });
    assert.equal((await page.getByTestId('sticky-pending').innerText()).trim(), 'Đủ 2/2 tiêu chí');
    assert.equal(await page.getByTestId('sticky-confirm').isDisabled(), true, `${viewport.label}: nothing left to confirm`);
    assert.equal(await page.getByTestId('sticky-reject').isDisabled(), true, `${viewport.label}: nothing left to reject`);

    assert.deepEqual(unexpected, [], `${viewport.label}: all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  console.log('Sticky review bar: pending count and confirm/reject reachable at 390px and 1440px: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
