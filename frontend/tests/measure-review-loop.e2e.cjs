/**
 * Đo baseline vòng duyệt một hồ sơ 6 tiêu chí — chạy trước khi sửa gì, để lần
 * cải tiến sau có số mà so.
 *
 * Ba số cần đo:
 *  - số phím HR phải bấm để duyệt hết 6 tiêu chí rồi sang hồ sơ kế;
 *  - số lần gọi API trong cả vòng (tách GET/POST);
 *  - thời gian từ hồ sơ này sang hồ sơ kế.
 *
 * Hồ sơ dùng để đo là app-0 trong fixture sẵn có; mock không có hồ sơ 6 tiêu chí
 * nên script tự nối thêm c5, c6 vào đúng response của app-0 (không sửa fixture
 * dùng chung, không thêm endpoint). Thời gian lấy từ hai nguồn: đồng hồ của
 * script và event PROFILE_OPENED/PROFILE_CLOSED mà chính app ghi qua
 * `recordUxEvent` (localStorage `hra-ux-events`).
 *
 * Chạy: HRA_E2E_BASE_URL=... node tests/measure-review-loop.e2e.cjs
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const CRITERIA_TOTAL = 6;
const EXTRA_RESULTS = [
  {
    result_id: 'app-0:r-c5', hr_reviews: [], criterion_id: 'c5', criterion_name: 'Kinh nghiệm CI/CD và hạ tầng dưới dạng mã',
    category: 'MUST_HAVE', outcome: 'MATCH', score: 74, confidence: 0.7, decision_source: 'AI',
    evidence_strength: 0.6, requires_verification: true, page_number: 5,
    reasoning: 'Có nhắc pipeline và Terraform nhưng không nêu quy mô.',
    verbatim_quote: 'Dựng pipeline GitHub Actions và hạ tầng Terraform cho ba môi trường.',
    evidence: [{ evidence_id: 'e5', verbatim_quote: 'Dựng pipeline GitHub Actions và hạ tầng Terraform cho ba môi trường.', page_number: 5, verification_status: 'UNVERIFIED' }],
  },
  {
    result_id: 'app-0:r-c6', hr_reviews: [], criterion_id: 'c6', criterion_name: 'Kinh nghiệm làm việc với đội sản phẩm',
    category: 'NICE_TO_HAVE', outcome: 'UNCLEAR', score: null, confidence: 0.42, decision_source: 'AI',
    evidence_strength: 0.3, requires_verification: true, page_number: 6,
    reasoning: 'Chỉ nêu "phối hợp với PM", không có ví dụ cụ thể.',
    verbatim_quote: 'Phối hợp với PM và designer để chốt phạm vi từng sprint.',
    evidence: [{ evidence_id: 'e6', verbatim_quote: 'Phối hợp với PM và designer để chốt phạm vi từng sprint.', page_number: 6, verification_status: 'UNVERIFIED' }],
  },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'measure-review-loop');
    localStorage.setItem('hra_locale', 'vi');
    localStorage.removeItem('hra-ux-events');
  });
  const unexpected = await installMockApi(context);

  // Lấy đúng body mà mock sẵn có trả cho app-0 (fetch qua route của mock, trước
  // khi cài handler nối thêm tiêu chí), rồi nối thêm c5/c6.
  const primer = await context.newPage();
  await primer.goto(`${base}/positions/p1/applicants`, { waitUntil: 'domcontentloaded' });
  const sixCriteriaBody = await primer.evaluate(async () => {
    const response = await fetch('/v1/applications/app-0', { headers: { Authorization: 'Bearer measure' } });
    return response.json();
  });
  await primer.close();
  const existingResults = (sixCriteriaBody.latest_assessment?.criterion_results || [])
    .filter(result => !['c5', 'c6'].includes(result.criterion_id));
  assert.equal(existingResults.length, 4, 'fixture app-0 có 4 tiêu chí trước khi nối thêm');
  sixCriteriaBody.latest_assessment.criterion_results = [...existingResults.map(result => ({
    ...result,
    result_id: result.result_id || `app-0:${result.criterion_id}`,
    hr_reviews: result.hr_reviews || [],
    requires_verification: true,
  })), ...EXTRA_RESULTS];

  // Đăng ký sau installMockApi nên handler này thắng cho đúng một URL.
  await context.route('**/v1/applications/app-0', async route => {
    if (route.request().method() !== 'GET') return route.continue();
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(sixCriteriaBody) });
  });
  await context.addInitScript(() => localStorage.removeItem('hra-ux-events'));

  const page = await context.newPage();
  const apiCalls = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/v1/')) return;
    apiCalls.push({ method: request.method(), path: url.pathname });
  });
  page.on('requestfailed', request => {
    apiCalls.push({ method: request.method(), path: new URL(request.url()).pathname, outcome: 'ABORTED' });
  });

  const keys = [];
  const press = async key => { keys.push(key); await page.keyboard.press(key); };

  // --- Vào hồ sơ app-0 với đủ 6 tiêu chí -----------------------------------
  const openStart = Date.now();
  await page.goto(`${base}/positions/p1/applicants/app-0?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await page.getByTestId('sticky-pending').waitFor({ timeout: 10000 });
  const openMs = Date.now() - openStart;
  const callsAfterOpen = apiCalls.length;
  assert.match(await page.getByTestId('verification-progress').innerText(), new RegExp(`0/${CRITERIA_TOTAL}\\b`), 'hồ sơ đo phải có đúng 6 tiêu chí chờ');

  // --- Duyệt hết 6 tiêu chí: mỗi tiêu chí một phím xác nhận ----------------
  const loopStart = Date.now();
  let confirms = 0;
  for (let index = 0; index < CRITERIA_TOTAL; index += 1) {
    await press('1');
    confirms += 1;
    const beforeWait = apiCalls.length;
    await page.waitForFunction(
      expected => {
        const chip = document.querySelector('[data-testid="sticky-pending"]');
        const progress = document.querySelector('[data-testid="verification-progress"]');
        const text = `${chip ? chip.textContent : ''} ${progress ? progress.textContent : ''}`;
        return text.includes(`${expected}/${6}`);
      },
      confirms,
      { timeout: 5000 },
    );
    if (process.env.HRA_MEASURE_DEBUG) console.log('after confirm', confirms, apiCalls.slice(beforeWait).map(call => `${call.method} ${call.path}`));
  }
  const loopMs = Date.now() - loopStart;
  const pendingText = await page.getByTestId('sticky-pending').innerText();

  // --- Sang hồ sơ kế tiếp: một phím, đo thời gian tới khi hồ sơ mới dựng ---
  const navStart = Date.now();
  await press('n');
  // Hàng đợi NEEDS_VERIFICATION chỉ gồm hồ sơ bị gắn cờ, nên hồ sơ kế sau
  // app-0 là app-2 (app-1 đã đạt, không nằm trong hàng đợi này).
  const NEXT_APPLICATION = 'app-2';
  await page.waitForURL(new RegExp(`/applicants/${NEXT_APPLICATION}(\\?|$)`), { timeout: 10000 });
  await page.getByTestId('sticky-pending').waitFor({ timeout: 10000 });
  const navMs = Date.now() - navStart;

  const uxEvents = await page.evaluate(() => JSON.parse(localStorage.getItem('hra-ux-events') || '[]'));
  const opened = uxEvents.filter(event => event.type === 'PROFILE_OPENED');
  const closed = uxEvents.filter(event => event.type === 'PROFILE_CLOSED');
  const dwell = closed.find(event => event.application_id === 'app-0');
  const nextOpened = opened.find(event => event.application_id === NEXT_APPLICATION);
  // PROFILE_CLOSED mang đúng thời điểm rời trang, nên khoảng lặng tới lần mở kế là hiệu hai mốc.
  const uxGapMs = dwell && nextOpened ? nextOpened.at - dwell.at : null;

  const count = predicate => apiCalls.filter(predicate).length;
  const reviews = apiCalls.filter(call => call.method === 'POST' && /\/assessments\/results\/.+\/review$/.test(call.path));
  assert.equal(reviews.length, CRITERIA_TOTAL, 'mỗi tiêu chí đúng một lần ghi');
  assert.deepEqual(unexpected, [], `không có request lạ: ${unexpected.join(', ')}`);

  const summary = {
    criteria: CRITERIA_TOTAL,
    keys: keys.length,
    keySequence: keys,
    // Phím thừa: phím không phải một lần xác nhận và không phải bước sang hồ sơ kế.
    wastedKeys: keys.filter(key => !['1', 'n'].includes(key)).length,
    confirms,
    pendingAfterLoop: pendingText.replace(/\s+/g, ' ').trim(),
    apiCalls: {
      total: apiCalls.length,
      open: callsAfterOpen,
      reviewLoop: apiCalls.length - callsAfterOpen,
      get: count(call => call.method === 'GET'),
      post: count(call => call.method === 'POST'),
      reviewPosts: reviews.length,
      paths: apiCalls.reduce((acc, call) => {
        const key = `${call.method} ${call.path}`;
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {}),
    },
    timing: {
      profileOpenMs: openMs,
      sixConfirmMs: loopMs,
      perConfirmMs: Math.round((loopMs / CRITERIA_TOTAL) * 10) / 10,
      toNextProfileMs: navMs,
      toNextProfileFromUxEventsMs: uxGapMs,
      dwellApp0Ms: dwell ? dwell.duration_ms : null,
    },
    uxEvents: uxEvents.map(event => ({ type: event.type, application_id: event.application_id, duration_ms: event.duration_ms })),
  };

  console.log(`BASELINE ${JSON.stringify(summary)}`);
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
