/**
 * Đo chiều cao thanh dính của hồ sơ, nhất là ở 390px.
 *
 * Mục tiêu ở màn hẹp: Xác nhận và Đánh dấu sai cùng một hàng, nhãn ngắn, và số
 * hàng của thanh giảm. Đo đúng ba thứ đó — chiều cao (px và % màn hình), số hàng,
 * và hai nút quyết định có cùng `top` hay không — rồi in một dòng `STICKY {json}`
 * để so trước/sau trên cùng một bản mock.
 *
 * Đặt `HRA_E2E_STICKY_MAX_XS=<px>` để chốt trần chiều cao ở 390px; không đặt thì
 * chỉ in số (dùng cho lần đo "trước").
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const maxXs = Number(process.env.HRA_E2E_STICKY_MAX_XS || 0);

const barMetrics = page => page.evaluate(() => {
  const confirm = document.querySelector('[data-testid="sticky-confirm"]');
  if (!confirm) return null;
  let bar = confirm;
  while (bar && getComputedStyle(bar).position !== 'sticky') bar = bar.parentElement;
  if (!bar) return null;

  const rect = bar.getBoundingClientRect();
  const controls = [...bar.querySelectorAll('button, a, .MuiChip-root')];
  // Đếm hàng theo tâm dọc của từng phần tử, gom trong 6px: chip cao 24px và nút
  // cao 45px cùng một hàng có `top` khác nhau, nhưng tâm thì trùng. Đếm `top`
  // tuyệt đối sẽ báo nhiều hàng hơn thực tế.
  const clustered = [];
  for (const center of controls.map(node => { const r = node.getBoundingClientRect(); return r.top + r.height / 2; }).sort((a, b) => a - b)) {
    if (!clustered.length || center - clustered[clustered.length - 1] > 6) clustered.push(center);
  }
  const tops = clustered;
  const confirmRect = confirm.getBoundingClientRect();
  const rejectRect = document.querySelector('[data-testid="sticky-reject"]').getBoundingClientRect();

  return {
    height: Math.round(rect.height),
    percentOfViewport: Math.round((rect.height / window.innerHeight) * 1000) / 10,
    rows: tops.length,
    confirmRejectSameRow: Math.abs(confirmRect.top - rejectRect.top) < 2,
    controls: controls.length,
    horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
});

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  const measured = {};
  for (const viewport of [{ width: 390, height: 844, label: '390' }, { width: 1440, height: 900, label: '1440' }]) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'sticky-height');
      localStorage.setItem('hra_locale', 'vi');
    });
    const unexpected = await installMockApi(context);
    const page = await context.newPage();
    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');
    await page.waitForTimeout(300);

    const metrics = await barMetrics(page);
    assert.ok(metrics, `${viewport.label}: thanh dính phải có nút xác nhận`);
    measured[viewport.label] = metrics;

    // Hai thứ phải đúng ở mọi khổ màn hình, trước và sau khi làm gọn.
    assert.equal(metrics.horizontalOverflow, false, `${viewport.label}: không tràn ngang`);
    for (const testId of ['sticky-confirm', 'sticky-reject']) {
      const box = await page.getByTestId(testId).boundingBox();
      assert.ok(box && box.width >= 40 && box.height >= 28, `${viewport.label}: ${testId} vẫn là nút bấm được (${Math.round(box?.width)}×${Math.round(box?.height)})`);
      assert.ok(box.x >= 0 && box.x + box.width <= viewport.width, `${viewport.label}: ${testId} nằm trong khổ ngang`);
    }
    assert.deepEqual(unexpected, [], `${viewport.label}: all API calls are accounted for: ${unexpected.join(', ')}`);
    await page.close();
    await context.close();
  }

  console.log(`STICKY ${JSON.stringify(measured)}`);

  if (maxXs > 0) {
    assert.ok(measured['390'].height <= maxXs, `thanh dính ở 390px phải ≤ ${maxXs}px (đang ${measured['390'].height}px)`);
    assert.equal(measured['390'].confirmRejectSameRow, true, 'Xác nhận và Đánh dấu sai phải cùng một hàng ở 390px');
  }

  console.log('Sticky bar measured on a narrow and a wide viewport: OK');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
