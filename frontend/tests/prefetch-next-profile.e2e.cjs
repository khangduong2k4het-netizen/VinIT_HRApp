/**
 * Tải trước dữ liệu hồ sơ kế tiếp: đo thời gian mở hồ sơ kế, không chỉ tin là có.
 *
 * Trang hồ sơ hiện spinner cho tới khi `GET /v1/applications/{id}` xong, nên mốc
 * đo là: từ lúc bấm `n` tới lúc hồ sơ kế vẽ được nội dung (tên ứng viên + thẻ
 * tiêu chí). Mock giữ request hồ sơ kế 600ms — nếu bản tải trước không được dùng,
 * mốc này không thể thấp hơn 600ms.
 *
 * Mỗi lần chời hồ sơ chỉ được một request hồ sơ: bản tải trước vừa xong trong
 * vài giây thì trang vẽ luôn bằng nó, **không** xác nhận lại bằng `GET` thứ hai
 * cho cùng dữ liệu. Kịch bản thứ hai kiểm chiều ngược lại: bản tải trước đã cũ
 * hơn cửa sổ đó thì trang vẫn đọc lại API (trong khi vẫn vẽ ngay từ bản cũ).
 *
 * Chạy 3 lần, lấy trung vị (một lần chạy đơn lẻ không nói được gì trên máy chia
 * sẻ). In một dòng `PREFETCH {json}` để so giữa hai bản.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi, detail, CRITERIA } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const nextApplicantId = 'app-8';
const nextApplicantName = 'Ngô Thanh Tùng';
const dataDelayMs = 600;
const runs = 3;
// Cùng giá trị với PREFETCH_REUSE_MS trong src/lib/profilePrefetch.ts: trong cửa
// sổ này bản tải trước được dùng luôn, không gọi lại API.
const reuseWindowMs = 5_000;

// Hồ sơ kế tiếp trả lời chậm như một lần gọi thật qua mạng, và mỗi lần gọi được
// ghi lại để biết lần vẽ đến từ bản tải trước hay từ chính request này.
function delayedDetail(onServed) {
  return async route => {
    await new Promise(resolve => setTimeout(resolve, dataDelayMs));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...detail,
        application_id: nextApplicantId,
        candidate_name: nextApplicantName,
        identity: { ...detail.identity, display_name: nextApplicantName },
        latest_assessment: {
          ...detail.latest_assessment,
          application_id: nextApplicantId,
          criterion_results: CRITERIA.map(c => ({ ...c, result_id: `${nextApplicantId}:${c.result_id}`, hr_reviews: [] })),
        },
      }),
    });
    onServed();
  };
}

const usable = page => page.evaluate(() => Boolean(
  document.querySelector('[data-testid="evidence-card"]')
  && document.body.innerText.includes('Ngô Thanh Tùng'),
));

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  const samples = [];
  for (let run = 0; run < runs; run += 1) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'prefetch-next');
      localStorage.setItem('hra_locale', 'vi');
    });

    let servedCount = 0;
    let firstServed;
    const served = new Promise(resolve => { firstServed = resolve; });
    const unexpected = await installMockApi(context, {
      [`/v1/applications/${nextApplicantId}`]: delayedDetail(() => {
        servedCount += 1;
        firstServed();
      }),
    });

    const page = await context.newPage();
    const apiCalls = [];
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.startsWith('/v1/')) apiCalls.push({ method: request.method(), path: url.pathname, at: Date.now() });
    });

    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');

    // Việc tải trước chạy khi trình duyệt rảnh, nên phải chờ chính request đó xong
    // thay vì đoán một khoảng thời gian.
    await served;
    assert.ok(servedCount >= 1, 'hồ sơ kế tiếp được tải trước khi HR bấm gì');

    await page.evaluate(() => {
      window.__navigationStartedAt = 0;
      window.addEventListener('keydown', () => {
        if (!window.__navigationStartedAt) window.__navigationStartedAt = performance.now();
      }, true);
    });

    await page.keyboard.press('n');
    await page.waitForFunction(
      () => Boolean(document.querySelector('[data-testid="evidence-card"]'))
        && document.body.innerText.includes('Ngô Thanh Tùng'),
      undefined,
      { timeout: 10000 },
    );
    const usableMs = await page.evaluate(() => Math.round(performance.now() - window.__navigationStartedAt));
    assert.ok(await usable(page), 'hồ sơ kế tiếp đã vẽ xong nội dung');

    // Bản tải trước vừa xong nên trang không được xác nhận lại ngay: đúng một
    // request hồ sơ cho cả lần mở, không phải hai (bản tải trước + bản đọc lại).
    await page.waitForTimeout(dataDelayMs + 300);
    const nextDetailCalls = apiCalls.filter(call => call.method === 'GET' && call.path === `/v1/applications/${nextApplicantId}`);
    assert.equal(nextDetailCalls.length, 1, `một lần mở hồ sơ kế chỉ được một GET hồ sơ, thấy ${nextDetailCalls.length}`);
    assert.equal(servedCount, 1, 'không có request hồ sơ kế nào ngoài lần tải trước');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);

    samples.push(usableMs);
    await page.close();
    await context.close();
  }

  const sorted = [...samples].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  console.log(`PREFETCH ${JSON.stringify({ runs: samples, median, dataDelayMs })}`);

  // Bản tải trước phải thắng chính độ trễ của request: nếu lần vẽ vẫn chờ request
  // hồ sơ kế thì mốc này không thể dưới 600ms.
  assert.ok(median < dataDelayMs, `mở hồ sơ kế không chờ request dữ liệu (trung vị ${median}ms < ${dataDelayMs}ms)`);
  for (const sample of samples) {
    assert.ok(sample < dataDelayMs, `mọi lần đo đều nhanh hơn request dữ liệu (${sample}ms)`);
  }

  // --- Kịch bản 2: bản tải trước đã cũ thì phải đọc lại API --------------
  // Chờ quá cửa sổ dùng lại rồi mới bấm `n`: trang vẫn vẽ ngay bằng bản tải trước
  // (không quay lại spinner), nhưng phải xác nhận lại với backend vì dữ liệu đã
  // cũ hơn cửa sổ đó.
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'prefetch-stale');
      localStorage.setItem('hra_locale', 'vi');
    });
    let servedCount = 0;
    let firstServed;
    const served = new Promise(resolve => { firstServed = resolve; });
    const unexpected = await installMockApi(context, {
      [`/v1/applications/${nextApplicantId}`]: delayedDetail(() => { servedCount += 1; firstServed(); }),
    });
    const page = await context.newPage();
    const apiCalls = [];
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.startsWith('/v1/')) apiCalls.push({ method: request.method(), path: url.pathname });
    });

    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');
    await served;
    await page.waitForTimeout(reuseWindowMs + 1_000);

    const startedAt = await page.evaluate(() => performance.now());
    await page.keyboard.press('n');
    await page.waitForFunction(
      () => Boolean(document.querySelector('[data-testid="evidence-card"]'))
        && document.body.innerText.includes('Ngô Thanh Tùng'),
      undefined,
      { timeout: 10000 },
    );
    const staleUsableMs = await page.evaluate(since => Math.round(performance.now() - since), startedAt);
    assert.ok(staleUsableMs < dataDelayMs, `bản cũ vẫn vẽ ngay chứ không chờ request (${staleUsableMs}ms)`);

    await page.waitForTimeout(dataDelayMs + 300);
    const detailCalls = apiCalls.filter(call => call.method === 'GET' && call.path === `/v1/applications/${nextApplicantId}`);
    assert.equal(detailCalls.length, 2, `bản tải trước đã cũ thì phải đọc lại API (thấy ${detailCalls.length} GET)`);
    assert.equal(servedCount, 2, 'cả hai request đều tới mock');
    assert.deepEqual(unexpected, [], `all API calls are accounted for: ${unexpected.join(', ')}`);
    console.log(`PREFETCH_STALE ${JSON.stringify({ staleUsableMs, detailRequests: detailCalls.length })}`);
    await page.close();
    await context.close();
  }

  console.log('Next profile opens from its prefetched data without a second read when fresh, and revalidates when stale: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
