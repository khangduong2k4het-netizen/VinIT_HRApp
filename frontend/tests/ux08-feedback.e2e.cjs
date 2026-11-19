/**
 * UX-08 / 3.9 — mọi thao tác async phải nói rõ kết quả, và nói được cho screen reader.
 *
 * Ba điều được khoá, mỗi điều từng sai:
 *  1. Lưu scorecard trước đây IM LẶNG: spinner dừng, không câu nào. HR không phân
 *     biệt được "đã lưu" với "bấm hụt".
 *  2. Vùng thông báo phải có mặt TRƯỚC khi có thông báo, nếu không screen reader
 *     đăng ký quá muộn và bỏ lỡ câu đầu tiên. (MUI <Snackbar> chỉ mount nội dung
 *     khi `open` — đó đúng là cách bản đầu tiên hỏng.)
 *  3. Trang shortlist từng crash "Application error" chỉ vì một request lỗi trả về
 *     object thay vì mảng. Một trang danh sách không được sập vì chuyện đó.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'ux08');
    localStorage.setItem('hra_locale', 'vi');
  });

  const json = (r, body, status = 200) => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  let savedPayload = null;
  await context.route('**/v1/**', async r => {
    const p = new URL(r.request().url()).pathname;
    if (p === '/v1/auth/me') return json(r, { user_id: 'u-hr', email: 'hr@vinuni.edu.vn', display_name: 'HR', roles: ['HR_RECRUITER'] });
    if (p === '/v1/shortlist/shared-with-me') return json(r, []);
    if (p === '/v1/scorecards/reminders') return json(r, []);
    if (p === '/v1/scorecards/share/share-1') {
      return json(r, [{
        scorecard_id: 'sc-1', application_id: 'app-1', status: 'IN_PROGRESS', revision: 1,
        due_at: '2031-01-01T00:00:00Z', can_edit: true, waiting_for_assessment: false,
        criteria_version_id: 'criteria', assessment_id: 'assessment',
        strengths: '', concerns: '', overall_recommendation: null,
        criteria: [{ criterion_id: 'c1', name: 'Python', description: 'Test', rating: null, insufficient_evidence: false }],
      }]);
    }
    if (p === '/v1/scorecards/sc-1') {
      savedPayload = r.request().postDataJSON();
      return json(r, {
        scorecard_id: 'sc-1', application_id: 'app-1', status: 'IN_PROGRESS', revision: 2,
        due_at: '2031-01-01T00:00:00Z', can_edit: true, waiting_for_assessment: false,
        criteria_version_id: 'criteria', assessment_id: 'assessment',
        strengths: '', concerns: '', overall_recommendation: null,
        criteria: [{ criterion_id: 'c1', name: 'Python', description: 'Test', rating: null, insufficient_evidence: false }],
      }, 201);
    }
    return json(r, {});
  });

  const page = await context.newPage();
  const crashes = [];
  page.on('pageerror', e => crashes.push(String(e.message).slice(0, 120)));

  // --- 1. The list page must survive a load, not die on a bad payload -------
  await page.goto(`${base}/shortlist`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  assert.deepEqual(crashes, [], `the shortlist index must not crash on load: ${crashes.join(' | ')}`);
  assert.doesNotMatch(await page.evaluate(() => document.body.innerText), /Application error/);

  // --- 2. Live regions exist before any message ---------------------------
  await page.goto(`${base}/shortlist/share-1`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  const regions = await page.evaluate(() => [...document.querySelectorAll('[data-testid^="action-feedback-"]')]
    .map(el => ({
      testid: el.getAttribute('data-testid'),
      role: el.getAttribute('role'),
      live: el.getAttribute('aria-live'),
      text: (el.textContent || '').trim(),
    })));
  assert.equal(regions.length, 2, `expected persistent success+error regions, got ${JSON.stringify(regions)}`);
  assert.deepEqual(regions.map(r => r.role).sort(), ['alert', 'status']);
  assert.deepEqual(regions.map(r => r.live).sort(), ['assertive', 'polite']);
  assert.deepEqual(regions.map(r => r.text), ['', ''], 'regions stay empty until there is something to say');

  // --- 3. Saving a scorecard now says so, inside the polite region --------
  await page.getByRole('button', { name: 'Lưu nháp scorecard' }).first().click();
  const success = page.getByTestId('action-feedback-success');
  await success.getByText(/Đã lưu nháp scorecard/).waitFor({ timeout: 8000 });
  assert.ok(savedPayload, 'the save must actually reach the API before we claim success');
  assert.equal(await success.getAttribute('aria-live'), 'polite');

  assert.deepEqual(crashes, [], `no page error during the flow: ${crashes.join(' | ')}`);
  console.log('UX-08: persistent live region, silent save now announces success, list survives a bad payload: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
