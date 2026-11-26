/**
 * Đo riêng đường đi "danh sách ứng viên → hồ sơ": bấm một dòng trong danh sách
 * thì trang hồ sơ phải gọi những API nào.
 *
 * Từ khi danh sách để lại thứ tự hồ sơ trong sessionStorage, trang hồ sơ dựng
 * được bộ đếm "hồ sơ k/n" và prev/next mà không phải gọi lại
 * `GET /v1/assessments/ranking/latest/{position}` và cả danh sách
 * `GET /v1/applications`. Script đo đúng hai request đó, kèm **đối chứng**: mở
 * cùng URL hồ sơ đó ở một tab mới (sessionStorage rỗng, như link gửi cho đồng
 * nghiệp), buộc trang hồ sơ dựng lại hàng đợi từ ranking + danh sách. Nếu đối
 * chứng không thấy hai request ấy thì phép đo không chứng minh được gì.
 *
 * Xoá sessionStorage rồi bấm link trong cùng tab **không** phải đối chứng:
 * `onClick` của link ghi lại ngữ cảnh ngay trước khi điều hướng, nên tab vẫn có
 * đủ thứ tự hồ sơ. Vì vậy đối chứng phải là một tab mới.
 *
 * Mỗi nhánh chạy vài lần và báo trung vị, vì con số đếm được vẫn có thể phụ
 * thuộc việc trang đã tải trước hồ sơ kế hay chưa.
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/list-to-profile-requests.cjs
 * In một dòng `LIST_TO_PROFILE {json}`.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { installMockApi } = require('./fixtures/hr-screens.cjs');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const RUNS = Number(process.env.HRA_LIST_TO_PROFILE_RUNS || 3);
const RANKING_PATH = '/v1/assessments/ranking/latest/p1';
const LIST_PATH = '/v1/applications';

const median = values => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2);
};

const countBy = (requests, predicate) => requests.filter(predicate).length;

const collect = page => {
  const requests = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/v1/')) requests.push({ method: request.method(), path: url.pathname });
  });
  return requests;
};

const measure = async (browser, { coldTab }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'list-to-profile');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = await installMockApi(context);
  const listPage = await context.newPage();
  await listPage.goto(`${base}/positions/p1/applicants?queue=NEEDS_VERIFICATION&sort=REVIEW_PRIORITY`, { waitUntil: 'networkidle' });
  await listPage.locator('table tbody tr').first().waitFor();
  const href = await listPage.locator('table tbody tr a[href*="/applicants/app-"]').first().getAttribute('href');

  let page = listPage;
  let requests;
  if (coldTab) {
    // Tab mới không có sessionStorage của tab danh sách: đúng cảnh một link hồ sơ
    // được mở riêng, nên trang phải tự dựng lại hàng đợi từ URL.
    await listPage.close();
    page = await context.newPage();
    requests = collect(page);
    await page.goto(`${base}${href}`, { waitUntil: 'networkidle' });
  } else {
    requests = collect(page);
    // Cửa sổ đo mở sau khi danh sách đã dựng xong: chỉ đếm request do việc mở hồ
    // sơ sinh ra, không đếm request của chính danh sách.
    await listPage.locator('table tbody tr a[href*="/applicants/app-"]').first().click();
  }
  const profilePath = new URL(href, base).pathname;
  await page.waitForURL(url => url.pathname === profilePath);
  // Chờ hồ sơ thật sự dựng xong (bộ đếm + thẻ bằng chứng), không chỉ URL đổi.
  await page.getByTestId('verification-progress').waitFor();
  await page.locator('[data-testid="evidence-card"]').first().waitFor();
  // Trang hồ sơ tải trước dữ liệu hồ sơ kế khi trình duyệt rảnh; chờ nó xong để
  // con số không phụ thuộc lúc nào trình duyệt thấy rảnh.
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1200);

  const gets = requests.filter(request => request.method === 'GET');
  // Request của khung ứng dụng (đăng nhập, huy hiệu việc cần làm) không phải do
  // việc mở hồ sơ sinh ra. Tab mới phải dựng lại khung nên có thêm work-queue;
  // tách chúng ra thì hai nhánh mới so được đúng thứ khác nhau: ranking + danh sách.
  const SHELL_PATHS = ['/v1/auth/me', '/v1/dashboard/work-queue'];
  const profileRequests = gets.filter(request => !SHELL_PATHS.includes(request.path));
  const result = {
    href,
    totalGetRequests: gets.length,
    profileGetRequests: profileRequests.length,
    rankingRequests: countBy(gets, request => request.path === RANKING_PATH),
    applicantListRequests: countBy(gets, request => request.path === LIST_PATH),
    detailRequests: countBy(gets, request => request.path === `/v1/applications/${profilePath.split('/').pop()}`),
    byPath: gets.reduce((acc, request) => ({ ...acc, [request.path]: (acc[request.path] || 0) + 1 }), {}),
  };

  await context.close();
  assert.deepEqual(unexpected, [], `không được có request lạ: ${unexpected.join(', ')}`);
  return result;
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  const arms = {
    'tu-danh-sach': { coldTab: false, runs: [] },
    'doi-chung-tab-moi': { coldTab: true, runs: [] },
  };

  for (const [name, arm] of Object.entries(arms)) {
    for (let index = 0; index < RUNS; index += 1) {
      const run = await measure(browser, { coldTab: arm.coldTab });
      // Chốt chặn: nhánh "từ danh sách" không được gọi lại ranking/danh sách;
      // nhánh đối chứng phải gọi đúng một lần mỗi thứ, nếu không phép đo vô nghĩa.
      if (arm.coldTab) {
        assert.equal(run.rankingRequests, 1, `${name} phải dựng lại hàng đợi từ ranking đúng một lần`);
        assert.equal(run.applicantListRequests, 1, `${name} phải đọc lại danh sách đúng một lần`);
      } else {
        assert.equal(run.rankingRequests, 0, `${name} không được gọi lại ranking: ${JSON.stringify(run.byPath)}`);
        assert.equal(run.applicantListRequests, 0, `${name} không được gọi lại danh sách: ${JSON.stringify(run.byPath)}`);
      }
      arm.runs.push({ run: index + 1, ...run });
    }
  }

  const summary = Object.fromEntries(Object.entries(arms).map(([name, arm]) => [name, {
    runs: arm.runs.length,
    medianTotalGetRequests: median(arm.runs.map(run => run.totalGetRequests)),
    medianProfileGetRequests: median(arm.runs.map(run => run.profileGetRequests)),
    totals: arm.runs.map(run => run.totalGetRequests),
    profileTotals: arm.runs.map(run => run.profileGetRequests),
    rankingRequests: arm.runs[0].rankingRequests,
    applicantListRequests: arm.runs[0].applicantListRequests,
    paths: arm.runs[0].byPath,
  }]));

  console.log(`LIST_TO_PROFILE ${JSON.stringify({ runs: arms, summary })}`);
  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
