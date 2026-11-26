/**
 * Đo vòng xác minh một hồ sơ: số phím HR phải bấm, số request mỗi lần xác nhận,
 * và việc CV có đi theo tiêu chí hay không.
 *
 *   node tests/review-loop-metrics.cjs   -> JSON ra stdout
 *
 * Chạy y hệt nhau trước và sau khi sửa để so sánh; mọi con số đều đọc từ màn
 * hình (chip tiến độ, thẻ đang chọn, trang của khung CV), không đọc state nội
 * bộ của app.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const pendingOf = async page => page.evaluate(() => {
  const chip = document.querySelector('[data-testid="verification-progress"]');
  const match = (chip?.textContent || '').match(/Đã xác minh (?:đủ )?(\d+)\/(\d+)/);
  return match ? { done: Number(match[1]), total: Number(match[2]) } : null;
});

/** Tiêu chí đang được con trỏ bàn phím chọn, đọc từ id của thẻ. */
const activeCriterion = async page => page.evaluate(() => {
  const card = document.querySelector('[data-testid="evidence-card"][data-active="true"]');
  return card ? card.id.replace(/^criterion-/, '') : null;
});

/** Trang CV đang mở: hash của iframe PDF, hoặc dòng "Trang N". */
const cvPageLabel = async page => page.evaluate(() => {
  const src = document.querySelector('#cv-pdf-viewer')?.getAttribute('src') || '';
  const fromHash = src.match(/#page=(\d+)/);
  if (fromHash) return Number(fromHash[1]);
  const fromText = document.body.innerText.match(/Trang (\d+)/);
  return fromText ? Number(fromText[1]) : null;
});

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  // Mỗi phần đo một context mới: mock giữ lại review đã ghi, dùng chung sẽ làm
  // phần sau bắt đầu với tiến độ khác 0.
  const openPage = async () => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await context.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'metrics');
      localStorage.setItem('hra_locale', 'vi');
      // Đếm cú bấm chuột thật: phần đo "một hồ sơ bằng bàn phím" phải chứng minh
      // không cần chuột, chứ không chỉ đếm phím.
      window.__clicks = 0;
      window.addEventListener('click', () => { window.__clicks += 1; }, true);
    });
    await installMockApi(context);
    const page = await context.newPage();
    const requests = [];
    page.on('request', request => {
      const url = new URL(request.url());
      requests.push({ method: request.method(), path: url.pathname, rsc: Boolean(request.headers()['next-router-prefetch']) });
    });
    await page.goto(`${base}/positions/p1/applicants/app-2?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="evidence-card"]');
    await page.waitForTimeout(400);
    const clicks = () => page.evaluate(() => window.__clicks || 0);
    return { page, context, requests, clicks };
  };

  const report = {};

  /**
   * Xác nhận hết tiêu chí bị gắn cờ. `firstKey` mô phỏng thao tác đầu tiên của
   * HR: bấm luôn, hoặc bấm j để xem tiêu chí kế trước khi quyết.
   * Khi một lần bấm không làm tiến độ đổi, HR phải tự chuyển tiêu chí rồi bấm
   * lại — chính số lần đó là thao tác thừa cần đo.
   */
  const runLoop = async (page, requests, firstKeys, label = 'vòng xác nhận') => {
    const start = requests.length;
    let keys = 0;
    let wasted = 0;
    for (const key of firstKeys) {
      await page.keyboard.press(key);
      keys += 1;
      await page.waitForTimeout(300);
    }
    let current = await pendingOf(page);
    const progress = [current];
    // Số request phát sinh sau mỗi lần bấm xác nhận. Đây là con số cần đọc khi
    // nghi ngờ "xác nhận xong lại tải lại hồ sơ": một lần xác nhận chỉ nên sinh
    // đúng một POST review.
    const requestsPerConfirm = [];
    let guard = 0;
    while (current && current.done < current.total && guard < 8) {
      guard += 1;
      const doneBefore = current.done;
      const beforePress = requests.length;
      await page.keyboard.press('1');
      keys += 1;
      await page.waitForTimeout(900);
      current = await pendingOf(page);
      progress.push(current);
      requestsPerConfirm.push(requests.length - beforePress);
      if (current.done === doneBefore) {
        wasted += 1;
        await page.keyboard.press('j');
        keys += 1;
        await page.waitForTimeout(300);
      }
    }
    const during = requests.slice(start);
    // Panel Profile ứng viên chỉ được tải khi HR mở accordion, không phải sau mỗi
    // lần xác nhận: profile và lịch sử trạng thái không được xuất hiện ở đây.
    const reloadedDuringLoop = during.filter(r => /^\/v1\/applications\/[^/]+\/(profile|status-events)$/.test(r.path));
    if (reloadedDuringLoop.length > 0) {
      throw Error(`${label}: xác nhận tiêu chí kéo theo tải lại ${[...new Set(reloadedDuringLoop.map(r => r.path))].join(', ')} (${reloadedDuringLoop.length} lần) — đúng lỗi cần chặn`);
    }
    const countByPath = during
      .filter(r => r.method === 'GET' && r.path.startsWith('/v1/'))
      .reduce((acc, r) => ({ ...acc, [r.path]: (acc[r.path] || 0) + 1 }), {});
    return {
      keysPressed: keys,
      pressesThatDidNothing: wasted,
      progress,
      requestsPerConfirm,
      profileOrHistoryRequests: reloadedDuringLoop.length,
      getRequestCounts: countByPath,
      getRequests: during.filter(r => r.method === 'GET' && r.path.startsWith('/v1/')).length,
      documentAndHistoryReloads: during.filter(r => r.method === 'GET' && /^\/v1\/applications\/app-2(\/status-events)?$/.test(r.path)).length,
      postRequests: during.filter(r => r.method === 'POST').length,
      getPaths: [...new Set(during.filter(r => r.method === 'GET' && r.path.startsWith('/v1/')).map(r => r.path))],
      activeCriterionAtEnd: await activeCriterion(page),
    };
  };

  // --- 1. Xác nhận liên tiếp, không chọn tay -------------------------------
  {
    const { page, context, requests } = await openPage();
    report.withoutSelection = await runLoop(page, requests, []);
    report.withoutSelection.nextRouteRequestsOnMount = requests.filter(r => r.path === '/positions/p1/applicants/app-8').length;
    await page.close();
    await context.close();
  }

  // --- 2. Có chọn tiêu chí bằng j (đúng như dòng phím tắt hướng dẫn) -------
  {
    const { page, context, requests } = await openPage();
    report.withSelection = await runLoop(page, requests, ['j']);
    await page.close();
    await context.close();
  }

  // --- 3. CV đang mở thì con trỏ và CV có đi cùng nhau không --------------
  {
    const { page, context, requests } = await openPage();
    const cvBefore = requests.filter(r => r.path.endsWith('/cv-file')).length;
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1200);
    const openedCv = requests.filter(r => r.path.endsWith('/cv-file')).length;
    const pageBefore = await cvPageLabel(page);
    const activeBefore = await activeCriterion(page);
    await page.keyboard.press('1');
    await page.waitForTimeout(900);
    report.cvFollow = {
      cvRequestsBeforeEnter: cvBefore,
      cvRequestsAfterEnter: openedCv,
      activeBefore,
      cvPageBefore: pageBefore,
      activeAfterConfirm: await activeCriterion(page),
      cvPageAfterConfirm: await cvPageLabel(page),
      requestsAfterConfirm: requests.slice(-12).map(r => `${r.method} ${r.path}`),
      progressAfterConfirm: await pendingOf(page),
    };
    await page.close();
    await context.close();
  }

  // --- 4. Sang hồ sơ kế tiếp: đã tải trước chưa, mất bao lâu --------------
  {
    const { page, context, requests } = await openPage();
    report.nextProfile = {
      requestsBeforePress: requests.filter(r => r.path === '/positions/p1/applicants/app-8').map(r => (r.rsc ? 'rsc-prefetch' : 'document')),
    };
    const startedAt = Date.now();
    await page.keyboard.press('n');
    await page.waitForFunction(() => /Ngô Thanh Tùng/.test(document.body.innerText), undefined, { timeout: 15000 });
    report.nextProfile.msUntilNextProfileNamed = Date.now() - startedAt;
    report.nextProfile.requestsAfterPress = requests
      .filter(r => r.path === '/positions/p1/applicants/app-8' || r.path === '/v1/applications/app-8')
      .map(r => `${r.method} ${r.path}`);
    await page.close();
    await context.close();
  }

  // --- 5. Panel Profile đang mở sẵn rồi xác nhận hết tiêu chí --------------
  // Đây là cấu hình mà lỗi "mount lại panel sau mỗi lần render" sẽ lộ ra: panel
  // đang mở, mỗi request /profile phát sinh thêm trong lúc xác nhận là một lần
  // mount lại. Vì vậy kịch bản này chặn bằng chính chốt chặn của runLoop, với
  // nhãn nói rõ panel đang mở — nếu panel bị gắn lại, test fail ngay chứ không
  // âm thầm tăng số request.
  {
    const { page, context, requests } = await openPage();
    const profileGets = () => requests.filter(r => /^\/v1\/applications\/[^/]+\/profile$/.test(r.path));
    const panelToggle = page.getByRole('button', { name: /^Profile ứng viên/ });
    const openedProfile = page.waitForResponse(res => /\/profile$/.test(new URL(res.url()).pathname) && res.status() === 200);
    await panelToggle.click();
    await openedProfile;
    // Panel phải thật sự đang mở và đã nạp xong nội dung, không phải chỉ là cú bấm
    // vừa gửi request: nếu chưa nạp xong thì kịch bản đo nhằm sai thời điểm.
    assert.equal(await panelToggle.getAttribute('aria-expanded'), 'true', 'panel Profile phải đang mở trước khi xác nhận');
    await page.locator('.MuiAccordionDetails-root .MuiCircularProgress-root').waitFor({ state: 'detached' });
    const profileGetsOnOpen = profileGets().length;
    assert.equal(profileGetsOnOpen, 1, `mở panel Profile đúng một lần tải: ${JSON.stringify(requests.map(r => r.path))}`);

    const loopStart = requests.length;
    const loop = await runLoop(page, requests, [], 'panel Profile đang mở');
    const profileDuringConfirm = requests
      .slice(loopStart)
      .filter(r => /^\/v1\/applications\/[^/]+\/profile$/.test(r.path)).length;
    assert.equal(profileDuringConfirm, 0, 'panel đang mở thì xác nhận không được tải lại /profile');
    assert.equal(await panelToggle.getAttribute('aria-expanded'), 'true', 'panel vẫn mở sau khi xác nhận hết tiêu chí');

    report.withProfilePanelOpen = {
      profileRequestsOnOpen: profileGetsOnOpen,
      profileRequestsDuringConfirm: profileDuringConfirm,
      panelStillExpanded: true,
      ...loop,
    };
    await page.close();
    await context.close();
  }

  // --- 6. Một hồ sơ trọn vẹn bằng bàn phím: `1` cho tiêu chí, `f` hoàn tất ---
  // Trước đây bàn phím dừng ở tiêu chí cuối: muốn "Đã xử lý xong" phải rời bàn
  // phím sang chuột. Đo đúng chỗ đó — số phím, số cú bấm chuột, và `?` có mở
  // được bảng phím tắt hay không.
  {
    const { page, context, clicks } = await openPage();
    let keys = 0;
    let progress = await pendingOf(page);
    while (progress && progress.done < progress.total) {
      await page.keyboard.press('1');
      keys += 1;
      await page.waitForTimeout(900);
      progress = await pendingOf(page);
    }
    const clicksBeforeFinish = await clicks();

    // `?` mở bảng phím tắt, và bảng phải nói về `f`; Esc phải đóng được nó.
    await page.keyboard.press('?');
    keys += 1;
    const helpOpened = await page.getByTestId('shortcuts-dialog').waitFor({ timeout: 5000 }).then(() => true).catch(() => false);
    const helpText = helpOpened
      ? (await page.getByTestId('shortcuts-dialog').innerText()).replace(/\s+/g, ' ').trim()
      : '';
    await page.keyboard.press('Escape');
    await page.getByTestId('shortcuts-dialog').waitFor({ state: 'detached', timeout: 5000 }).catch(() => {});
    const helpClosed = (await page.getByTestId('shortcuts-dialog').count()) === 0;

    // `f` phải làm đúng việc của nút "Đã xử lý xong": mở hộp thoại hoàn tất hoặc
    // đi thẳng sang hồ sơ kế. Ở hồ sơ này (IN_REVIEW, điểm 69) là hộp thoại.
    await page.keyboard.press('f');
    keys += 1;
    let finishDialogOpened = await page.getByTestId('finish-dialog').waitFor({ timeout: 6000 }).then(() => true).catch(() => false);
    let navigated = finishDialogOpened
      ? false
      : await page.waitForFunction(() => !window.location.pathname.endsWith('/applicants/app-2'), undefined, { timeout: 3000 }).then(() => true).catch(() => false);
    const finishByKey = finishDialogOpened || navigated;
    // Bản chưa có phím `f`: đo luôn đường phải dùng thay thế (chuột) để bảng
    // trước/sau có cùng đơn vị — số phím *và* số cú bấm. Trên bản có `f` nhánh
    // này không chạy.
    if (!finishByKey) {
      await page.getByTestId('finish-application').click();
      finishDialogOpened = await page.getByTestId('finish-dialog').waitFor({ timeout: 6000 }).then(() => true).catch(() => false);
      navigated = finishDialogOpened
        ? false
        : await page.waitForFunction(() => !window.location.pathname.endsWith('/applicants/app-2'), undefined, { timeout: 3000 }).then(() => true).catch(() => false);
    }
    report.keyboardProfile = {
      keysPressed: keys,
      // Phím đã bấm mà không làm gì: `?` không mở bảng, `f` không hoàn tất.
      deadKeys: (helpOpened ? 0 : 1) + (finishByKey ? 0 : 1),
      finishByKey,
      clicksDuringFinish: (await clicks()) - clicksBeforeFinish,
      finishDialogOpened,
      navigatedToNextProfile: navigated,
      shortcutsHelpOpened: helpOpened,
      shortcutsHelpClosedByEscape: helpClosed,
      shortcutsHelpMentionsFinish: /f —/.test(helpText),
      shortcutsHelpText: helpText.slice(0, 160),
    };
    await page.close();
    await context.close();
  }

  console.log(JSON.stringify(report, null, 2));

  // Assert của phần 6 nằm sau khi in số, để một lần chạy trên bản cũ vẫn cho ra
  // bảng trước/sau trước khi fail.
  assert.equal(report.keyboardProfile.shortcutsHelpOpened, true, '`?` phải mở bảng phím tắt');
  assert.ok(report.keyboardProfile.shortcutsHelpMentionsFinish, `bảng phím tắt phải có dòng về \`f\`: ${report.keyboardProfile.shortcutsHelpText}`);
  assert.equal(report.keyboardProfile.shortcutsHelpClosedByEscape, true, 'Esc phải đóng bảng phím tắt');
  assert.equal(report.keyboardProfile.finishByKey, true, '`f` phải hoàn tất được hồ sơ mà không cần chuột');
  assert.equal(report.keyboardProfile.clicksDuringFinish, 0, 'hoàn tất bằng bàn phím không được cần cú bấm chuột');
  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
