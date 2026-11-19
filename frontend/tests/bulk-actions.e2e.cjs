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

  console.log('Bulk actions: any screening row selectable, NEW shortlisted through NEW → IN_REVIEW → SHORTLIST with the dialog saying so, reject with one shared reason, one existing endpoint per record: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
