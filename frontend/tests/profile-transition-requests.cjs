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

  // Hai trần chờ, chỉ để báo lỗi rõ khi môi trường treo — không dùng để "đoán"
  // thời điểm. Bình thường mọi sự kiện dưới đây tới trong vài chục mili giây.
  const NOTES_IDLE_TIMEOUT_MS = 5_000;
  const EVENT_TIMEOUT_MS = 10_000;

  // Ghi chú đang bay hay chưa, theo đúng sự kiện mạng thay vì một khoảng ngủ.
  const notesInFlight = new Set();
  const notePath = url => new URL(url).pathname;
  const isNote = path => path.endsWith('/private-notes');
  page.on('request', request => {
    const path = notePath(request.url());
    if (isNote(path)) notesInFlight.add(path);
  });
  page.on('response', response => {
    const path = notePath(response.url());
    if (isNote(path)) notesInFlight.delete(path);
  });
  page.on('requestfailed', request => {
    const path = notePath(request.url());
    if (isNote(path)) notesInFlight.delete(path);
  });
  const waitForNotesIdle = async () => {
    const deadline = Date.now() + NOTES_IDLE_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (notesInFlight.size === 0) return;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error(
      `vẫn còn request ghi chú đang bay sau ${NOTES_IDLE_TIMEOUT_MS} ms: ${[...notesInFlight].join(', ')}`,
    );
  };

  await page.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await page.locator('table tbody tr').first().waitFor();
  await page.locator('table tbody tr a[href*="/applicants/app-"]').first().click();
  await page.getByTestId('verification-progress').waitFor();
  await page.locator('[data-testid="evidence-card"]').first().waitFor();
  await page.waitForLoadState('networkidle');
  // Rubric của lần mở đầu tiên không tính vào phép đo chuyển hồ sơ.
  await page.waitForTimeout(400);

  const openedId = new URL(page.url()).pathname.split('/').pop();
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
    const toId = new URL(page.url()).pathname.split('/').pop();
    transitions.push({
      from,
      to: await profileName(page),
      toId,
      notes: during.filter(path => path.endsWith('/private-notes')).map(path => path.split('/')[3]),
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

  // --- Hai trường hợp còn lại, đo riêng vì cần thời điểm khác nhau -----------
  // (a) HR ở lại một hồ sơ lâu hơn cửa sổ dùng chung của `auth/me` (30 giây).
  // (b) HR bấm `n` trước khi việc nạp ghi chú theo nhịp rảnh kịp chạy.
  // Mỗi lần chỉ đo một lần chuyển, cùng cách đếm `GET /v1/` như trên.
  const openFresh = async () => {
    const freshContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await freshContext.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'transition-requests');
      localStorage.setItem('hra_locale', 'vi');
    });
    const freshUnexpected = await installMockApi(freshContext);
    const freshPage = await freshContext.newPage();
    const gets = [];
    const notesOffProfile = [];
    freshPage.on('request', request => {
      const url = new URL(request.url());
      if (!url.pathname.startsWith('/v1/') || request.method() !== 'GET') return;
      gets.push(url.pathname);
      if (url.pathname.endsWith('/private-notes')) {
        // Hồ sơ đang xem tại đúng thời điểm request được gửi.
        const viewed = new URL(freshPage.url()).pathname.split('/').pop();
        const askedFor = url.pathname.split('/')[3];
        if (askedFor !== viewed) notesOffProfile.push({ askedFor, viewed });
      }
    });
    await freshPage.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await freshPage.locator('table tbody tr').first().waitFor();
    await freshPage.locator('table tbody tr a[href*="/applicants/app-"]').first().click();
    await freshPage.getByTestId('verification-progress').waitFor();
    await freshPage.locator('[data-testid="evidence-card"]').first().waitFor();
    await freshPage.waitForLoadState('networkidle');
    await freshPage.waitForTimeout(400);
    return { freshContext, freshPage, gets, notesOffProfile, freshUnexpected };
  };

  const moveOn = async (freshPage, name) => {
    await freshPage.waitForFunction(previous => {
      const heading = document.querySelector('h1');
      return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== previous);
    }, name, { timeout: 15000 });
    await freshPage.getByTestId('verification-progress').waitFor();
    await freshPage.locator('[data-testid="evidence-card"]').first().waitFor();
    await freshPage.waitForLoadState('networkidle');
  };

  // (a) Ở lại 32 giây rồi mới chuyển: bản dùng chung `auth/me` đã hết hạn.
  const dwellArm = await openFresh();
  const dwellName = await profileName(dwellArm.freshPage);
  await dwellArm.freshPage.waitForTimeout(32_000);
  const dwellStart = dwellArm.gets.length;
  await dwellArm.freshPage.keyboard.press('n');
  await moveOn(dwellArm.freshPage, dwellName);
  await dwellArm.freshPage.waitForTimeout(400);
  const dwellGets = dwellArm.gets.slice(dwellStart);
  const dwellAuth = dwellGets.filter(path => path === '/v1/auth/me').length;

  // (b) Bấm `n` liền hai lần, trước khi nhịp rảnh kịp nạp ghi chú của hồ sơ vừa mở.
  const fastArm = await openFresh();
  const fastFirst = await profileName(fastArm.freshPage);
  fastArm.notesOffProfile.length = 0;
  await fastArm.freshPage.keyboard.press('n');
  await fastArm.freshPage.waitForTimeout(70);
  await fastArm.freshPage.keyboard.press('n');
  await moveOn(fastArm.freshPage, fastFirst);
  await fastArm.freshPage.waitForTimeout(800);
  const fastNotesOffProfile = fastArm.notesOffProfile.slice();

  await dwellArm.freshContext.close();
  await fastArm.freshContext.close();

  // Đổi hồ sơ trong cùng một vị trí không đổi quyền của HR: ở lại hồ sơ lâu hơn
  // 30 giây rồi bấm `n` cũng không được hỏi lại danh tính hay badge công việc.
  assert.equal(
    dwellAuth,
    0,
    `chuyển hồ sơ trong cùng vị trí không được hỏi lại auth/me (đã ở lại 32 giây), thấy ${JSON.stringify(dwellGets)}`,
  );
  assert.equal(
    dwellGets.filter(path => path === '/v1/dashboard/work-queue').length,
    0,
    `chuyển hồ sơ trong cùng vị trí không được tải lại badge công việc, thấy ${JSON.stringify(dwellGets)}`,
  );
  // Chuyển nhanh (trước khi nhịp rảnh nạp ghi chú) không được gửi request ghi
  // chú cho hồ sơ không còn trong tầm nhìn.
  assert.deepEqual(
    fastNotesOffProfile,
    [],
    `không được hỏi ghi chú của hồ sơ đang không hiển thị, thấy ${JSON.stringify(fastNotesOffProfile)}`,
  );

  // Lần chuyển đầu có thể cần rubric; các lần sau trong cùng vị trí thì không.
  // Nếu cache rubric không hoạt động, mọi lần chuyển đều có đúng 1 request.
  const rubricPerTransition = transitions.map(transition => transition.rubric);
  console.log(`TRANSITIONS ${JSON.stringify({
    transitions,
    rubricPerTransition,
    authPerTransition: transitions.map(transition => transition.auth),
    totalGetPerTransition: transitions.map(transition => transition.totalGet),
    fullLoopGetRequests: transitions.reduce((sum, transition) => sum + transition.totalGet, 0),
    dwellAfterSharedAuthExpired: { auth: dwellAuth, paths: dwellGets },
    fastTransitions: { notesOffProfile: fastNotesOffProfile },
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

  // Ghi chú: mỗi lần chuyển tải ghi chú của hồ sơ **vừa mở** đúng một lần, và
  // không hỏi ghi chú của hồ sơ vừa rời. Ghi chú tải sau khi hồ sơ dùng được
  // (~180 ms), nên cửa sổ đo của lần chuyển có đúng request của hồ sơ mới.
  const leftIds = [openedId, ...transitions.slice(0, -1).map(transition => transition.toId)];
  transitions.forEach((transition, index) => {
    assert.deepEqual(
      transition.notes,
      [transition.toId],
      `lần chuyển ${index + 1} phải tải ghi chú của hồ sơ vừa mở (${transition.toId}) đúng một lần, thấy ${JSON.stringify(transition.notes)}`,
    );
    assert.ok(
      !transition.notes.includes(leftIds[index]),
      `lần chuyển ${index + 1} không được hỏi ghi chú của hồ sơ vừa rời (${leftIds[index]})`,
    );
  });

  // Ghi chú tải đúng một lần: mở panel chỉ hiện bản đã tải, không hỏi lại.
  const notesRequestsBeforePanel = requests.filter(path => path.endsWith('/private-notes')).length;
  await page.getByRole('button', { name: /Ghi chú nội bộ HR/ }).click();
  await page.getByText('Chưa có ghi chú nội bộ.').waitFor({ timeout: 5000 });
  await page.waitForTimeout(300);
  assert.equal(
    requests.filter(path => path.endsWith('/private-notes')).length,
    notesRequestsBeforePanel,
    'mở panel ghi chú không được phát sinh thêm request tải ghi chú',
  );

  // Ba lần chuyển đã đi hết hàng đợi; lùi hai hồ sơ để còn hồ sơ kế cho kịch
  // bản dưới. Lùi bằng history (không tải lại trang) nên ngữ cảnh hàng đợi giữ nguyên.
  for (let back = 0; back < 2; back += 1) {
    const beforeBack = await profileName(page);
    await page.goBack();
    await page.waitForFunction(name => {
      const heading = document.querySelector('h1');
      return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== name);
    }, beforeBack, { timeout: 15000 });
    await page.getByTestId('verification-progress').waitFor();
  }
  // Ghi chú của hồ sơ vừa lùi về phải tải xong trước khi đo request kế tiếp:
  // chờ trạng thái "không còn request ghi chú nào đang bay", không ngủ cố định.
  await waitForNotesIdle();

  // Rời hồ sơ khi request ghi chú còn đang bay: request phải bị huỷ. Không dựa
  // vào một con số mili giây để biết nó "còn đang bay": route dưới đây giữ mọi
  // request ghi chú cho tới khi test mở cổng, và cổng chỉ mở sau khi đã rời hồ
  // sơ. Nhờ vậy thứ tự sự kiện quyết định, không phải tốc độ máy.
  let openGate;
  const gate = new Promise(resolve => { openGate = resolve; });
  await page.route('**/v1/applications/*/private-notes', async route => {
    await gate;
    // Request đã bị huỷ thì fulfill ném lỗi; đó là kết quả mong đợi ở đây.
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }).catch(() => {});
  });
  const notesStarted = page.waitForRequest(
    request => isNote(notePath(request.url())),
    { timeout: EVENT_TIMEOUT_MS },
  );
  await page.keyboard.press('n');
  const inFlightPath = notePath((await notesStarted).url());
  const leavingFrom = await profileName(page);
  // Đăng ký cả hai sự kiện trước cú bấm thứ hai: chúng có thể tới ngay sau đó.
  // Kết quả nào tới trước là câu trả lời — huỷ, hay vẫn được trả lời.
  const abortEvent = page.waitForEvent('requestfailed', {
    predicate: request => notePath(request.url()) === inFlightPath,
    timeout: EVENT_TIMEOUT_MS,
  });
  const answerEvent = page.waitForResponse(
    response => notePath(response.url()) === inFlightPath,
    { timeout: EVENT_TIMEOUT_MS },
  );
  await page.keyboard.press('n');
  await page.waitForFunction(name => {
    const heading = document.querySelector('h1');
    return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== name);
  }, leavingFrom, { timeout: 15000 });
  // Mở cổng sau khi đã rời hồ sơ: nếu request không bị huỷ, nó hoàn tất ngay và
  // phép race dưới đây thấy câu trả lời — không cần chờ thêm khoảng nào.
  openGate();
  const outcome = await Promise.race([
    abortEvent.then(request => ({ kind: 'aborted', error: request.failure()?.errorText || '' })),
    answerEvent.then(response => ({ kind: 'answered', status: response.status() })),
  ]).catch(error => {
    throw new Error(
      `không thấy ghi chú ${inFlightPath} bị huỷ hay được trả lời trong ${EVENT_TIMEOUT_MS} ms: ${error.message}`,
    );
  });
  assert.equal(
    outcome.kind,
    'aborted',
    `rời hồ sơ phải huỷ request ghi chú ${inFlightPath}, nhưng nó vẫn được trả lời (${outcome.status})`,
  );
  assert.match(
    outcome.error,
    /ABORTED/i,
    `request bị huỷ phải là ERR_ABORTED, thấy ${outcome.error}`,
  );


  await page.close();
  await context.close();
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
