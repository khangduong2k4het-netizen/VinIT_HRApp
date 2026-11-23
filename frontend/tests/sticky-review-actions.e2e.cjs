/**
 * Thanh dính trên hồ sơ phải trả lời được hai câu ngay tại chỗ, không cần cuộn:
 * còn bao nhiêu tiêu chí chờ, và quyết định cho tiêu chí đang chọn là gì.
 *
 * Trước đây cả hai nằm trong thẻ bằng chứng: HR đọc CV ở cột phải, thẻ đang xem
 * đã trôi khỏi màn hình (trên điện thoại càng rõ), muốn xác nhận phải cuộn
 * ngược lên đúng thẻ.
 *
 * Kiểm ở 390, 768, 1024 và 1440px. Hai đầu là màn hẹp/desktop; hai khổ giữa
 * (máy tính bảng dọc và ngang) là chỗ dễ lọt bản rút gọn nhãn hoặc rơi mất một
 * nút xuống hàng dưới, nên chúng nằm trong cùng phép kiểm: cùng một bộ từ và
 * hai nút cùng hàng ở mọi khổ.
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

  const labelSets = {};
  const viewports = [
    { width: 390, height: 844, label: '390' },
    { width: 768, height: 1024, label: '768' },
    { width: 1024, height: 768, label: '1024' },
    { width: 1440, height: 900, label: '1440' },
  ];
  const buttonRows = {};
  for (const viewport of viewports) {
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
    const buttonBoxes = {};
    for (const testId of ['sticky-confirm', 'sticky-reject']) {
      const button = page.getByTestId(testId);
      assert.equal(await button.isVisible(), true, `${viewport.label}: ${testId} visible`);
      const box = await button.boundingBox();
      assert.ok(box, `${viewport.label}: ${testId} has a box`);
      assert.ok(box.y >= 0 && box.y + box.height <= viewport.height, `${viewport.label}: ${testId} is on screen (y=${Math.round(box.y)})`);
      assert.ok(box.x >= 0 && box.x + box.width <= viewport.width, `${viewport.label}: ${testId} is inside the width`);
      buttonBoxes[testId] = box;
    }
    // Hai nút quyết định phải cùng một hàng: so đường tâm chứ không so mép trên,
    // vì nút viền (Đánh dấu sai) cao hơn nút đặc một hai pixel do đường viền.
    const centerY = box => box.y + box.height / 2;
    const rowOffset = Math.abs(centerY(buttonBoxes['sticky-confirm']) - centerY(buttonBoxes['sticky-reject']));
    assert.ok(
      rowOffset <= 2,
      `${viewport.label}: hai nút cùng hàng (lệch tâm ${rowOffset.toFixed(1)}px)`,
    );
    buttonRows[viewport.label] = { center: centerY(buttonBoxes['sticky-confirm']), offset: rowOffset };
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, `${viewport.label}: no horizontal overflow`);

    // --- Cùng một bộ từ ở mọi khổ -------------------------------------------
    // `Đúng`/`Sai` ở màn hẹp đọc như kết luận về tiêu chí, và đổi sang
    // `Xác nhận`/`Đánh dấu sai` từ 600px là hai bộ từ cho cùng một hành động.
    // Nhãn đầy đủ vừa một hàng ở 390px nên không cần bản rút gọn nào.
    const labels = {
      confirm: (await page.getByTestId('sticky-confirm').innerText()).trim(),
      reject: (await page.getByTestId('sticky-reject').innerText()).trim(),
    };
    assert.deepEqual(labels, { confirm: 'Xác nhận', reject: 'Đánh dấu sai' }, `${viewport.label}: nhãn hành động đầy đủ`);
    labelSets[viewport.label] = labels;

    // --- Đang quyết định cho tiêu chí nào, đọc được trên thanh --------------
    // Tooltip không hiện trên điện thoại, nên tên tiêu chí phải nằm sẵn trên thanh.
    const criterionChip = page.getByTestId('sticky-criterion');
    assert.equal(await criterionChip.isVisible(), true, `${viewport.label}: criterion name is on the bar`);
    assert.match((await criterionChip.innerText()).trim(), /^Đang chọn: Kinh nghiệm dẫn dắt|^Đang chọn: Thiết kế/, `${viewport.label}: criterion name text`);
    const chipBox = await criterionChip.boundingBox();
    assert.ok(chipBox.x >= 0 && chipBox.x + chipBox.width <= viewport.width, `${viewport.label}: criterion name fits the width`);
    assert.ok(chipBox.height <= 30, `${viewport.label}: criterion name stays on one line (h=${Math.round(chipBox.height)})`);
    assert.equal(
      await criterionChip.evaluate(el => getComputedStyle(el.querySelector('.MuiChip-label')).textOverflow),
      'ellipsis',
      `${viewport.label}: long names are cut with an ellipsis, not wrapped`,
    );
    const activeBeforeConfirm = (await criterionChip.innerText()).trim();

    // --- Xác nhận từ thanh dính: ghi nhận và chuyển tiêu chí ---------------
    assert.equal(await page.getByTestId('sticky-confirm').isDisabled(), false, `${viewport.label}: active criterion can be confirmed`);
    await page.getByTestId('sticky-confirm').click();
    await page.waitForFunction(() => /Đã xác minh 1\/2/.test(document.querySelector('[data-testid="verification-progress"]')?.textContent || ''), undefined, { timeout: 8000 });
    assert.equal((await page.getByTestId('sticky-pending').innerText()).trim(), 'Còn 1/2 tiêu chí chờ');
    assert.equal(await progressText(page), '1/2');
    assert.equal(reviewPosts.length, 1, `${viewport.label}: one recorded review`);
    const activeAfterConfirm = (await page.getByTestId('sticky-criterion').innerText()).trim();
    assert.notEqual(activeAfterConfirm, activeBeforeConfirm, `${viewport.label}: the bar follows the next criterion`);
    assert.match(activeAfterConfirm, /^Đang chọn: /, `${viewport.label}: next criterion is named too`);

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

  for (const viewport of viewports) {
    assert.deepEqual(
      labelSets[viewport.label],
      labelSets['390'],
      `${viewport.label}px phải dùng cùng bộ từ như 390px cho Xác nhận / Đánh dấu sai`,
    );
  }
  assert.deepEqual(
    Object.keys(buttonRows),
    viewports.map(viewport => viewport.label),
    'đo được hàng của hai nút ở mọi khổ',
  );
  console.log(`Sticky review bar: pending count, one label set, confirm/reject on one row at ${viewports.map(v => `${v.label}px`).join(', ')}: OK`);
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
