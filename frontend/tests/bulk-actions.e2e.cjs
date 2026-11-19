/**
 * Bulk actions on the ranking list.
 *
 * The reviewer used to open one profile at a time to shortlist or reject, and a
 * row could only be selected if it was already shortlisted (that checkbox was
 * for sharing). Now every row still in screening can be selected, and one
 * floating bar offers shortlist / reject for the whole selection.
 *
 * Guardrails checked here, because each would be a real defect:
 *  1. Rows that are not shortlisted — including a NEW application — are
 *     selectable.
 *  2. A bulk shortlist walks NEW rows through the two valid steps
 *     (NEW → IN_REVIEW → SHORTLIST) using the same endpoint, says so in the
 *     dialog, and reports already-shortlisted rows as skipped instead of forcing
 *     an invalid transition.
 *  3. A bulk rejection cannot be confirmed without a shared reason, and that
 *     reason goes out with every record.
 *  4. The batch uses the existing per-application status endpoint and nothing
 *     else; no new API surface is invented.
 *  5. On a 390px and a 360px phone the floating bar spans the screen, every
 *     action and the confirm button are at least 44px tall and fully on screen,
 *     and the last application clears the bar instead of sitting underneath it.
 *  6. While the batch runs, the dialog names the record being written. A record
 *     that fails after its first step reports the reason and where it stopped,
 *     and "retry the failures" touches exactly that record and only the step it
 *     never reached — it does not re-run the records that already succeeded.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
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
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'bulk');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const page = await context.newPage();

  const statusPatches = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    const match = path.match(/^\/v1\/applications\/(app-\d+)\/status$/);
    if (match && request.method() === 'PATCH') {
      statusPatches.push({ id: match[1], body: JSON.parse(request.postData() || '{}') });
    }
  });

  const rowCheckbox = name => page.getByRole('checkbox', { name: `Chọn hồ sơ ${name}` });
  const bar = page.getByTestId('bulk-action-bar');
  const dialog = page.getByTestId('bulk-dialog');
  // The banner is set after the ranking reloads, which happens just after the
  // bar disappears: wait for the text instead of assuming an ordering.
  const waitForNotice = text => page.waitForFunction(
    expected => (document.querySelector('[data-testid="action-feedback-success"]')?.textContent || '').includes(expected),
    text,
    { timeout: 15000 },
  );

  await page.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="applicant-count"]');
  await page.waitForSelector('tbody tr');

  // --- 1. Any screening row can be selected -------------------------------
  assert.equal(await rowCheckbox('Nguyễn Minh Anh').isEnabled(), true, 'an In review row is selectable');
  assert.equal(await rowCheckbox('Trần Quốc Bảo').isEnabled(), true, 'a Shortlisted row is still selectable');
  assert.equal(await rowCheckbox('Phan Trọng Nghĩa').isEnabled(), true, 'a NEW row is selectable');

  await rowCheckbox('Nguyễn Minh Anh').check(); // IN_REVIEW
  await rowCheckbox('Trần Quốc Bảo').check(); // SHORTLIST
  await rowCheckbox('Phan Trọng Nghĩa').check(); // NEW → shortlisted through two steps
  await bar.waitFor();
  assert.match(await page.getByTestId('bulk-selection-count').innerText(), /3 hồ sơ/);

  // --- 2. Bulk shortlist walks NEW through two valid steps ----------------
  assert.match(await page.getByTestId('bulk-shortlist-open').innerText(), /Shortlist 2 hồ sơ/);
  await page.getByTestId('bulk-shortlist-open').click();
  await dialog.waitFor();
  const twoStep = page.getByTestId('bulk-two-step');
  assert.match(await twoStep.innerText(), /1 hồ sơ đang ở trạng thái Mới/);
  assert.match(await twoStep.innerText(), /hai lần chuyển trạng thái/);
  assert.match(await dialog.innerText(), /Mới · 2 bước chuyển trạng thái/);
  assert.match(await page.getByTestId('bulk-skipped').innerText(), /Bỏ qua 1 hồ sơ/);
  await page.getByTestId('bulk-confirm').click();
  await bar.waitFor({ state: 'detached', timeout: 10000 });
  // One PATCH per step, in the only order the state machine allows.
  assert.deepEqual(statusPatches.map(call => [call.id, call.body.new_status]), [
    ['app-0', 'SHORTLIST'],
    ['app-11', 'IN_REVIEW'],
    ['app-11', 'SHORTLIST'],
  ]);
  await waitForNotice('hai lần chuyển trạng thái');
  assert.match(await page.getByTestId('action-feedback-success').innerText(), /Đã shortlist 2 hồ sơ/);

  // --- 3 + 4. Bulk rejection needs one shared reason, sent per record -----
  statusPatches.length = 0;
  await rowCheckbox('Lê Thu Hà').check(); // IN_REVIEW
  await rowCheckbox('Phạm Đình Khang').check(); // IN_REVIEW
  await rowCheckbox('Phan Trọng Nghĩa').check(); // NEW
  await bar.waitFor();
  assert.match(await page.getByTestId('bulk-selection-count').innerText(), /3 hồ sơ/);

  await page.getByTestId('bulk-reject-open').click();
  await dialog.waitFor();
  assert.equal(await page.getByTestId('bulk-confirm').isDisabled(), true, 'a rejection without a reason stays blocked');
  const sharedReason = 'Không đáp ứng yêu cầu bắt buộc về số năm kinh nghiệm.';
  await page.getByLabel('Lý do chung (bắt buộc)').fill(sharedReason);
  await page.getByTestId('bulk-confirm').click();
  await bar.waitFor({ state: 'detached', timeout: 10000 });

  assert.deepEqual(statusPatches.map(call => call.id), ['app-2', 'app-3', 'app-11']);
  assert.equal(statusPatches.every(call => call.body.new_status === 'REJECTED_SCREENING'), true);
  assert.equal(statusPatches.every(call => call.body.reason === sharedReason), true);
  await waitForNotice('Đã cập nhật 3 hồ sơ');
  assert.match(await page.getByTestId('action-feedback-success').innerText(), /Đã cập nhật 3 hồ sơ/);

  assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

  // --- 6. Per-record progress, a real stopping point, and retry of failures only --
  // One In review record is deliberately slow, so the progress line is observable;
  // one New record fails on its second step, so it has a real stopping point.
  let shortlistAttempts = 0;
  const retryContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await retryContext.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'bulk-retry');
    localStorage.setItem('hra_locale', 'vi');
  });
  const retryUnexpected = await installMockApi(retryContext, {
    '/v1/applications/app-2/status': async r => {
      await new Promise(resolve => setTimeout(resolve, 1500));
      const body = JSON.parse(r.request().postData() || '{}');
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ application_id: 'app-2', application_status: body.new_status }) });
    },
    '/v1/applications/app-11/status': async r => {
      const body = JSON.parse(r.request().postData() || '{}');
      if (body.new_status === 'SHORTLIST' && shortlistAttempts === 0) {
        shortlistAttempts += 1;
        return r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Máy chủ đang bận, vui lòng thử lại.' }) });
      }
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ application_id: 'app-11', application_status: body.new_status }) });
    },
  });
  const retryPage = await retryContext.newPage();
  const retryCalls = [];
  retryPage.on('request', request => {
    const path = new URL(request.url()).pathname;
    const match = path.match(/^\/v1\/applications\/(app-\d+)\/status$/);
    if (match && request.method() === 'PATCH') retryCalls.push([match[1], JSON.parse(request.postData() || '{}').new_status]);
  });
  const retryBox = name => retryPage.getByRole('checkbox', { name: `Chọn hồ sơ ${name}` });

  await retryPage.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
  await retryPage.waitForSelector('[data-testid="applicant-count"]');
  await retryBox('Lê Thu Hà').check(); // app-2, IN_REVIEW, slow but succeeds
  await retryBox('Phan Trọng Nghĩa').check(); // app-11, NEW, fails on the second step
  await retryPage.getByTestId('bulk-action-bar').waitFor();
  await retryPage.getByTestId('bulk-shortlist-open').click();
  await retryPage.getByTestId('bulk-dialog').waitFor();
  await retryPage.getByTestId('bulk-confirm').click();

  // The progress line names the record being written, not only a count.
  await retryPage.getByTestId('bulk-progress').waitFor({ timeout: 5000 });
  assert.match(await retryPage.getByTestId('bulk-progress').innerText(), /Đang xử lý 1\/2: Lê Thu Hà/);

  // The failing New record stopped after In review: reason and stopping point per row.
  const stop = retryPage.getByTestId('bulk-row-stop-app-11');
  await stop.waitFor({ timeout: 20000 });
  assert.match(await stop.innerText(), /Đã ghi nhận bước Đang xem, chưa tới Shortlist/);
  assert.match(await retryPage.getByTestId('bulk-row-error-app-11').innerText(), /Máy chủ đang bận/);
  assert.match(await retryPage.getByTestId('bulk-row-state-app-2').innerText(), /Xong/);
  assert.match(await retryPage.getByTestId('bulk-row-state-app-11').innerText(), /Lỗi/);
  assert.match(await retryPage.getByTestId('bulk-failure-summary').innerText(), /1\/2 hồ sơ đã cập nhật/);
  assert.deepEqual(retryCalls, [['app-2', 'SHORTLIST'], ['app-11', 'IN_REVIEW'], ['app-11', 'SHORTLIST']]);

  // Retry runs only the failed record, and only the step it never reached.
  retryCalls.length = 0;
  await retryPage.getByTestId('bulk-retry').click();
  await retryPage.getByTestId('bulk-dialog').waitFor({ state: 'detached', timeout: 20000 });
  assert.deepEqual(retryCalls, [['app-11', 'SHORTLIST']], 'retry must not repeat the record that already succeeded or the step already written');
  await retryPage.waitForFunction(
    () => (document.querySelector('[data-testid="action-feedback-success"]')?.textContent || '').includes('Đã shortlist 1 hồ sơ'),
    null,
    { timeout: 15000 },
  );
  assert.deepEqual(retryUnexpected, [], `retry context API calls are accounted for: ${retryUnexpected.join(', ')}`);
  await retryContext.close();

  // --- 5. On a phone the floating bar must not hide the list or shrink taps --
  // Measured before the fix at 390x844: the bar shrink-wrapped to 195px wide and
  // 311px tall, and the last visible application sat underneath it. The checks
  // below are about geometry, not styling taste: full-width bar, 44px targets,
  // and the last row reachable by scrolling.
  for (const viewport of [{ width: 390, height: 844 }, { width: 360, height: 640 }]) {
    const mobile = await browser.newContext({ viewport, isMobile: true, hasTouch: true });
    await mobile.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'bulk-mobile');
      localStorage.setItem('hra_locale', 'vi');
    });
    const mobileUnexpected = await installMockApi(mobile);
    const phone = await mobile.newPage();
    const phoneErrors = [];
    phone.on('pageerror', error => phoneErrors.push(String(error)));

    await phone.goto(`${base}/positions/p1/applicants`, { waitUntil: 'networkidle' });
    await phone.waitForSelector('[data-testid="applicant-count"]');
    await phone.getByRole('checkbox', { name: 'Chọn hồ sơ Nguyễn Minh Anh' }).check();
    await phone.waitForSelector('[data-testid="bulk-action-bar"]');

    // The list must be scrollable to a point where its last item is above the bar.
    await phone.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await phone.waitForTimeout(300);
    const geometry = await phone.evaluate(() => {
      const bar = document.querySelector('[data-testid="bulk-action-bar"]').getBoundingClientRect();
      const buttons = [...document.querySelectorAll('[data-testid="bulk-action-bar"] button')].map(button => {
        const rect = button.getBoundingClientRect();
        return { label: (button.textContent || '').trim(), height: Math.round(rect.height), left: Math.round(rect.left), right: Math.round(rect.right) };
      });
      const cards = [...document.querySelectorAll('a[href*="/applicants/app-"]')];
      const lastCard = cards[cards.length - 1].getBoundingClientRect();
      return {
        viewport: { width: innerWidth, height: innerHeight },
        bar: { left: Math.round(bar.left), right: Math.round(bar.right), height: Math.round(bar.height), top: Math.round(bar.top) },
        buttons,
        lastCardBottom: Math.round(lastCard.bottom),
      };
    });

    const label = `${viewport.width}x${viewport.height}`;
    assert.ok(geometry.bar.left <= 12 && geometry.bar.right >= geometry.viewport.width - 12,
      `${label}: the bar spans the screen, got ${geometry.bar.left}–${geometry.bar.right} of ${geometry.viewport.width}`);
    assert.ok(geometry.bar.height <= geometry.viewport.height * 0.4,
      `${label}: the bar must not eat the screen, got ${geometry.bar.height}px of ${geometry.viewport.height}px`);
    assert.equal(geometry.buttons.length, 4, `${label}: every batch action is reachable`);
    for (const button of geometry.buttons) {
      assert.ok(button.height >= 44, `${label}: "${button.label}" needs a 44px touch target, got ${button.height}px`);
      assert.ok(button.left >= 0 && button.right <= geometry.viewport.width,
        `${label}: "${button.label}" is fully on screen (${button.left}–${button.right})`);
    }
    assert.ok(geometry.lastCardBottom <= geometry.bar.top,
      `${label}: the last application must clear the bar, card ends at ${geometry.lastCardBottom}px, bar starts at ${geometry.bar.top}px`);

    // The confirmation itself is the button HR taps with a thumb.
    await phone.getByTestId('bulk-shortlist-open').click();
    await phone.getByTestId('bulk-dialog').waitFor();
    const confirmBox = await phone.getByTestId('bulk-confirm').boundingBox();
    assert.ok(confirmBox.height >= 44, `${label}: confirm needs a 44px touch target, got ${confirmBox.height}px`);
    assert.ok(confirmBox.y >= 0 && confirmBox.y + confirmBox.height <= viewport.height,
      `${label}: confirm is fully visible without scrolling`);
    assert.equal(await phone.getByTestId('bulk-confirm').isDisabled(), false, `${label}: confirm is tappable once opened`);
    await phone.getByRole('button', { name: 'Hủy' }).click();

    assert.deepEqual(phoneErrors, [], `${label}: no client-side exceptions: ${phoneErrors.join(' | ')}`);
    assert.deepEqual(mobileUnexpected, [], `${label}: all API calls are accounted for: ${mobileUnexpected.join(', ')}`);
    await mobile.close();
  }

  console.log('Bulk actions: any screening row selectable, NEW shortlisted through NEW → IN_REVIEW → SHORTLIST with the dialog saying so, reject with one shared reason, one existing endpoint per record; a failed New record reports its reason and stopping point and retry touches only that record and only its missing step; on 390px and 360px the bar spans the screen, targets are 44px, and the last application clears it: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
