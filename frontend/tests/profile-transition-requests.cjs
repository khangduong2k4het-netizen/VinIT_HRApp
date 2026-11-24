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

// Panel ghi chú đóng sẵn và chỉ tải khi mở; mở lần thứ hai sẽ đóng nó.
const openNotesPanel = async page => {
  const summary = page.getByRole('button', { name: /Ghi chú nội bộ HR/ }).first();
  await summary.waitFor({ timeout: 10000 });
  if ((await summary.getAttribute('aria-expanded')) !== 'true') await summary.click();
};

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
    const toId = new URL(page.url()).pathname.split('/').pop();
    // Ghi chú không còn tự tải khi mở hồ sơ, nên chuyển hồ sơ không phát sinh
    // request ghi chú nào. Chỉ chờ các request phụ (chi tiết hồ sơ kế, tải
    // trước) xong rồi mới chốt số.
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(200);

    const during = requests.slice(startedAt);
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

  // --- Lướt nhanh: không được hỏi ghi chú của hồ sơ vừa rời ------------------
  // HR thường bấm `n` liền tay khi hồ sơ không có gì để xem. Ghi chú là thông
  // tin phụ nên được nạp sau; nếu nạp quá sớm, mỗi hồ sơ lướt qua đều phát sinh
  // một request rồi bị huỷ — trên mạng vẫn là một request cho hồ sơ đã rời.
  const skimContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await skimContext.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'notes-skim');
    localStorage.setItem('hra_locale', 'vi');
  });
  const skimUnexpected = await installMockApi(skimContext);
  const skimPage = await skimContext.newPage();
  const skimNotes = [];
  skimPage.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (!path.endsWith('/private-notes')) return;
    skimNotes.push({
      askedFor: path.split('/')[3],
      viewedAtSend: new URL(skimPage.url()).pathname.split('/').pop(),
    });
  });
  await skimPage.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await skimPage.locator('table tbody tr').first().waitFor();
  await skimPage.locator('table tbody tr a[href*="/applicants/app-5"]').first().click();
  await skimPage.getByTestId('sticky-pending').waitFor({ timeout: 15000 });
  await skimPage.waitForLoadState('networkidle');
  skimNotes.length = 0;
  // Ba hồ sơ lướt qua, cách nhau 250 ms — nhanh hơn một lần đọc ghi chú.
  for (let skip = 0; skip < 3; skip += 1) {
    await skimPage.keyboard.press('n');
    await skimPage.waitForTimeout(250);
  }
  // Dừng lại đủ lâu để hồ sơ cuối nạp ghi chú của chính nó.
  await skimPage.waitForLoadState('networkidle');
  await skimPage.waitForTimeout(1500);
  const skimStoppedAt = new URL(skimPage.url()).pathname.split('/').pop();
  // Hồ sơ đã rời = hồ sơ không phải chỗ HR dừng lại. Đây là thứ phải bằng 0:
  // mỗi hồ sơ lướt qua từng tốn một GET ghi chú rồi bị huỷ.
  const skimLeftBehind = skimNotes.filter(entry => entry.askedFor !== skimStoppedAt);
  const skimOffProfile = skimNotes.filter(entry => entry.askedFor !== entry.viewedAtSend);
  // Lướt xong và dừng lại: vẫn chưa được có request nào. Chỉ khi HR mở panel của
  // hồ sơ đang xem mới có đúng một request — cho chính hồ sơ đó. Chốt lại con số
  // trước khi mở panel để báo cáo đọc được cả hai mốc, và để assert nằm sau
  // phần in (một lần chạy trên bản cũ vẫn in được số trước khi fail).
  const skimNotesBeforeOpen = skimNotes.slice();
  await openNotesPanel(skimPage);
  await skimPage.getByText('Chưa có ghi chú nội bộ.').waitFor({ timeout: 5000 });
  await skimPage.waitForTimeout(300);
  const skimNotesAfterOpen = skimNotes.slice();
  await skimContext.close();

  // --- Mở hồ sơ từ danh sách: tổng số lần hỏi auth/me ------------------------
  // Trang danh sách ứng viên tự hỏi danh tính để có bộ lọc "Của tôi"; khung
  // trang cũng hỏi. Hai chỗ cho cùng một câu trả lời, trong cùng một lần mở.
  const openFromList = await (async () => {
    const openContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await openContext.addInitScript(() => {
      localStorage.setItem('hra_access_token', 'open-from-list');
      localStorage.setItem('hra_locale', 'vi');
    });
    const openUnexpected = await installMockApi(openContext);
    const openPage = await openContext.newPage();
    const meCalls = [];
    openPage.on('request', request => {
      if (new URL(request.url()).pathname === '/v1/auth/me') meCalls.push(Date.now());
    });
    await openPage.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
    await openPage.locator('table tbody tr').first().waitFor();
    await openPage.waitForLoadState('networkidle');
    const beforeClick = meCalls.length;
    await openPage.locator('table tbody tr a[href*="/applicants/app-"]').first().click();
    await openPage.getByTestId('sticky-pending').waitFor({ timeout: 15000 });
    await openPage.waitForLoadState('networkidle');
    await openPage.waitForTimeout(500);
    const total = meCalls.length;
    await openContext.close();
    return { beforeClick, total, unexpected: openUnexpected.length };
  })();

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
    openFromList,
    skim: { beforeOpen: skimNotesBeforeOpen, afterOpen: skimNotesAfterOpen, leftBehind: skimLeftBehind, offProfile: skimOffProfile, stoppedAt: skimStoppedAt },
  })}`);

  // Mở hồ sơ từ danh sách: danh tính chỉ được hỏi một lần cho cả luồng.
  assert.ok(
    openFromList.total <= 1,
    `mở hồ sơ từ danh sách chỉ được hỏi auth/me tối đa một lần, thấy ${openFromList.total}`,
  );
  assert.equal(openFromList.unexpected, 0, 'luồng mở từ danh sách không có request lạ');

  // Lướt nhanh: chỉ hồ sơ HR dừng lại mới được hỏi ghi chú.
  assert.deepEqual(
    skimNotesBeforeOpen,
    [],
    `lướt 3 hồ sơ rồi dừng lại không được tải ghi chú, thấy ${JSON.stringify(skimNotesBeforeOpen)}`,
  );
  assert.deepEqual(
    skimNotesAfterOpen,
    [{ askedFor: skimStoppedAt, viewedAtSend: skimStoppedAt }],
    `mở panel sau khi lướt chỉ được hỏi ghi chú của hồ sơ đang xem (${skimStoppedAt}) đúng một lần, thấy ${JSON.stringify(skimNotesAfterOpen)}`,
  );
  assert.deepEqual(
    skimLeftBehind,
    [],
    `không được hỏi ghi chú của hồ sơ đã rời, thấy ${JSON.stringify(skimLeftBehind)}`,
  );

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

  // Ghi chú: KHÔNG tự tải khi mở hay chuyển hồ sơ. Trước đây hồ sơ HR dừng lại
  // vẫn tốn một request (sau 600 ms); nay chỉ panel ghi chú — nơi duy nhất đọc
  // dữ liệu — mới tải.
  const noteRequests = () => requests.filter(path => path.endsWith('/private-notes'));
  transitions.forEach((transition, index) => {
    assert.deepEqual(
      transition.notes,
      [],
      `lần chuyển ${index + 1} không được tải ghi chú, thấy ${JSON.stringify(transition.notes)}`,
    );
  });
  assert.deepEqual(noteRequests(), [], `mở/chuyển hồ sơ không được tải ghi chú: ${JSON.stringify(noteRequests())}`);
  // Số ghi chú chỉ biết được sau khi tải, nên chưa mở panel thì chưa có số.
  assert.equal(await page.getByTestId('hr-note-count').count(), 0, 'chưa mở panel thì chưa được hiện số ghi chú');

  // Mở panel: đúng một request, cho hồ sơ đang xem; đóng/mở lại không hỏi lại.
  const notesBeforePanel = noteRequests().length;
  const viewedId = new URL(page.url()).pathname.split('/').pop();
  await openNotesPanel(page);
  await page.getByText('Chưa có ghi chú nội bộ.').waitFor({ timeout: 5000 });
  await page.waitForTimeout(300);
  assert.deepEqual(
    noteRequests().slice(notesBeforePanel),
    [`/v1/applications/${viewedId}/private-notes`],
    `mở panel phải tải ghi chú của hồ sơ đang xem (${viewedId}) đúng một lần, thấy ${JSON.stringify(noteRequests())}`,
  );
  await page.getByRole('button', { name: /Ghi chú nội bộ HR/ }).click();
  await page.waitForTimeout(200);
  await page.getByRole('button', { name: /Ghi chú nội bộ HR/ }).click();
  await page.waitForTimeout(400);
  assert.equal(
    noteRequests().length,
    notesBeforePanel + 1,
    'đóng/mở lại panel không được tải lại ghi chú',
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
  // Ghi chú chỉ tải khi mở panel: mở panel để có một request đang bay rồi mới rời
  // hồ sơ. (Sau các lần lùi trang, trang được gắn lại nên panel đóng sẵn.)
  await openNotesPanel(page);
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



  // --- Ghi chú không mang sang hồ sơ kế -------------------------------------
  // Mock trả ghi chú riêng cho từng hồ sơ (app-5: 2, app-0: 1) và **giữ** câu
  // trả lời của app-0 cho tới khi test mở cổng. Nhờ vậy có một cửa sổ chắc chắn
  // để thấy: nếu state ghi chú không được xoá khi đổi hồ sơ, chip "2 ghi chú
  // riêng tư" và ghi chú của app-5 vẫn nằm trên app-0 trong lúc chờ dữ liệu mới.
  const makeNote = (note_id, content, criterion_id) => ({
    note_id,
    content,
    criterion_id,
    created_at: '2026-11-20T09:00:00Z',
    author_name: 'Nguyễn Thu Hằng',
  });
  const notesByProfile = {
    'app-5': [makeNote('n-5-1', 'Ghi chú chung của hồ sơ app-5', null), makeNote('n-5-2', 'Ghi chú tiêu chí của hồ sơ app-5', 'c2')],
    'app-0': [makeNote('n-0-1', 'Ghi chú tiêu chí của hồ sơ app-0', 'c2')],
  };
  let openNotesGate;
  const notesGate = new Promise(resolve => { openNotesGate = resolve; });
  const notesContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await notesContext.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'notes-carry');
    localStorage.setItem('hra_locale', 'vi');
  });
  const notesUnexpected = await installMockApi(notesContext, {
    '/v1/applications/app-5/private-notes': route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(notesByProfile['app-5']),
    }),
    '/v1/applications/app-0/private-notes': async route => {
      await notesGate;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(notesByProfile['app-0']),
      }).catch(() => {});
    },
  });
  const notesPage = await notesContext.newPage();
  const notesPageRequests = [];
  notesPage.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/private-notes')) notesPageRequests.push(path);
  });
  await notesPage.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION`, { waitUntil: 'networkidle' });
  await notesPage.locator('table tbody tr').first().waitFor();
  await notesPage.locator('table tbody tr a[href*="/applicants/app-5"]').first().click();
  await notesPage.getByTestId('sticky-pending').waitFor({ timeout: 15000 });
  // Mở hồ sơ không tự tải ghi chú: chưa mở panel thì chưa có request nào.
  assert.deepEqual(notesPageRequests, [], `mở hồ sơ app-5 không được tải ghi chú: ${JSON.stringify(notesPageRequests)}`);
  await openNotesPanel(notesPage);
  await notesPage.getByTestId('hr-note-count').waitFor({ timeout: 10000 });
  assert.match(
    (await notesPage.getByTestId('hr-note-count').innerText()).trim(),
    /^2 ghi chú riêng tư/,
    'hồ sơ app-5 phải hiện 2 ghi chú của chính nó trước khi chuyển',
  );
  await notesPage.getByText('Ghi chú tiêu chí của hồ sơ app-5').first().waitFor({ timeout: 5000 });

  const beforeSwitch = (await notesPage.locator('h1').innerText()).trim();
  await notesPage.keyboard.press('n');
  await notesPage.waitForFunction(name => {
    const heading = document.querySelector('h1');
    return Boolean(heading && heading.textContent.trim() && heading.textContent.trim() !== name);
  }, beforeSwitch, { timeout: 15000 });
  // Chuyển hồ sơ không hỏi ghi chú của hồ sơ mới: chỉ app-5 (lúc mở panel) đã hỏi.
  assert.deepEqual(
    notesPageRequests,
    ['/v1/applications/app-5/private-notes'],
    `chuyển hồ sơ không được tải ghi chú, thấy ${JSON.stringify(notesPageRequests)}`,
  );

  const oldCountGone = await notesPage.waitForFunction(
    () => document.querySelector('[data-testid="hr-note-count"]') === null,
    undefined,
    { timeout: 5000 },
  ).then(() => true).catch(() => false);
  assert.ok(oldCountGone, 'số ghi chú của hồ sơ cũ không được mang sang hồ sơ kế khi ghi chú mới chưa về');
  // Cùng một tiêu chí (c2): nếu ghi chú bị cộng dồn, chữ của hồ sơ cũ sẽ nằm
  // ngay cạnh tiêu chí trên hồ sơ kế.
  const oldNoteGone = await notesPage.waitForFunction(
    () => !document.querySelector('#criterion-c2')?.textContent?.includes('Ghi chú tiêu chí của hồ sơ app-5'),
    undefined,
    { timeout: 5000 },
  ).then(() => true).catch(() => false);
  assert.ok(oldNoteGone, 'ghi chú của hồ sơ cũ không được hiện cạnh tiêu chí trên hồ sơ kế');

  // Mở panel ghi chú của hồ sơ kế: request đi và bị cổng giữ, nên chưa hiện số.
  const app0NotesStarted = notesPage.waitForRequest(
    request => new URL(request.url()).pathname === '/v1/applications/app-0/private-notes',
    { timeout: EVENT_TIMEOUT_MS },
  );
  await openNotesPanel(notesPage);
  await app0NotesStarted;
  await notesPage.waitForTimeout(300);
  assert.equal(
    await notesPage.getByTestId('hr-note-count').count(),
    0,
    'ghi chú của hồ sơ mới chưa về thì chưa được hiện số',
  );
  // Mở cổng: hồ sơ kế hiện đúng ghi chú của chính nó (1), không cộng dồn với 2.
  openNotesGate();
  await notesPage.getByTestId('hr-note-count').waitFor({ timeout: 10000 });
  assert.match(
    (await notesPage.getByTestId('hr-note-count').innerText()).trim(),
    /^1 ghi chú riêng tư/,
    'hồ sơ kế chỉ được hiện ghi chú của chính nó',
  );
  await notesPage.locator('#criterion-c2').getByText('Ghi chú tiêu chí của hồ sơ app-0').first().waitFor({ timeout: 5000 });
  assert.equal(
    await notesPage.locator('#criterion-c2').getByText('Ghi chú tiêu chí của hồ sơ app-5').count(),
    0,
    'tiêu chí c2 của hồ sơ kế không được giữ ghi chú của hồ sơ cũ',
  );
  assert.deepEqual(notesUnexpected, [], `nhánh ghi chú có request lạ: ${notesUnexpected.join(', ')}`);
  await notesContext.close();

  await page.close();
  await context.close();
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
