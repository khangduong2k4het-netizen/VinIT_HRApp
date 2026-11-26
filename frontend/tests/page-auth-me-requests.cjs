/**
 * Đo `GET /v1/auth/me` khi **mở thẳng** một trang quản lý tài khoản và trang chi
 * tiết vị trí, sau khi hai trang này bỏ lời gọi `authApi.me()` riêng và dùng
 * `getCurrentUser()` dùng chung.
 *
 * Mỗi trang, khi mở, có hai nơi cùng cần biết "tôi là ai": khung ứng dụng
 * (`AppLayout`, kiểm tra quyền) và chính trang (`admin/users` để biết dòng nào
 * là tài khoản của mình, `positions/[id]` để biết vai trò theo vị trí). Trước
 * đây hai nơi hỏi riêng nên mở trang là **hai** request giống hệt nhau; nay
 * trang đọc bản dùng chung nên chỉ còn **một**.
 *
 * Phép đo này là đối chứng của chính nó: chạy trên bản hiện tại phải thấy 1,
 * chạy trên bản trước thay đổi (hai trang trả về lời gọi `authApi.me()`) phải
 * thấy 2. Vì vậy nó không chỉ đếm — nó còn chờ nội dung thật của trang hiện ra,
 * để con số 1 không phải vì danh tính không bao giờ được tải.
 *
 * Chạy: HRA_E2E_BASE_URL=http://127.0.0.1:3000 node tests/page-auth-me-requests.cjs
 * In một dòng `PAGE_AUTH_ME {json}`.
 */
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use local Next server only');
}

const RUNS = Number(process.env.HRA_PAGE_AUTH_RUNS || 2);
const AUTH_ME_PATH = '/v1/auth/me';

const me = {
  user_id: 'u-hr', display_name: 'Nguyễn Thu Hằng', email: 'hang@example.org',
  must_change_password: false,
  system_roles: ['ADMIN', 'HR_RECRUITER'], position_roles: ['HR_RECRUITER'],
  position_assignments: [{ position_id: 'p1', position_role: 'HR_RECRUITER' }],
};

const POSITION = {
  position_id: 'p1', position_code: 'REQ-2026-014',
  title: 'Senior Backend Engineer (Python)', status: 'OPEN',
  department_id: 'd1', department_name: 'Nền tảng & Hạ tầng', criteria_status: 'APPROVED',
};

// Vị trí vừa tạo, chưa có JD/tiêu chí: trang chi tiết vẫn phải dựng xong, và
// không kéo thêm request nào ngoài những đường đã mock.
const WORKSPACE = {
  position: { position_id: 'p1', position_code: 'REQ-2026-014', title: 'Senior Backend Engineer (Python)', status: 'OPEN', department_name: 'Nền tảng & Hạ tầng' },
  jd: { latest_version_id: null, version_number: null },
  criteria: { current_version_id: null, current_status: null, version_number: null, approved_for_latest_jd: false, is_stale_for_latest_jd: false },
  counts: { total: 0, assessed: 0, processing: 0, file_review: 0, not_assessed: 0, needs_verification: 0, possible_mismatch: 0, meets_mandatory: 0, duplicate_pending: 0, shortlisted: 0 },
  active_operation: null,
  workflow: {
    current_step: 'JD',
    steps: [{ code: 'JD', status: 'CURRENT' }, { code: 'CRITERIA', status: 'NOT_STARTED' }, { code: 'CV_INTAKE', status: 'NOT_STARTED' }, { code: 'HR_REVIEW', status: 'NOT_STARTED' }, { code: 'SHORTLIST', status: 'NOT_STARTED' }],
    next_action: { code: 'CREATE_JD', blocked_reason_code: null, target: { pathname: '/positions/p1', search: 'tab=jd' } },
  },
  viewer: { is_hr: true, is_hm: false, position_roles: ['HR_RECRUITER'], system_roles: ['ADMIN', 'HR_RECRUITER'] },
};

const ACCOUNTS = [
  { user_id: 'u-hr', email: 'hang@example.org', display_name: 'Nguyễn Thu Hằng', account_status: 'ACTIVE', roles: ['ADMIN', 'HR_RECRUITER'], must_change_password: false },
  { user_id: 'u-hm', email: 'hm@example.org', display_name: 'Trần Minh HM', account_status: 'ACTIVE', roles: ['HIRING_MANAGER'], must_change_password: false },
];

const RESPONSES = {
  [AUTH_ME_PATH]: () => me,
  '/v1/dashboard/work-queue': () => ({ generated_at: '2026-11-19T03:00:00Z', summary: {}, items: [] }),
  '/v1/admin/users': () => ({ items: ACCOUNTS, page: 1, has_more: false }),
  '/v1/positions/p1': () => POSITION,
  '/v1/criteria/position/p1/versions': () => [],
  '/v1/positions/p1/jd-versions': () => [],
  '/v1/positions/p1/workspace': () => WORKSPACE,
  '/v1/dashboard/position/p1': () => ({ total_applications: 0, applications_processing: 0, files_needing_hr_review: 0, applications_by_status: { SHORTLIST: 0 } }),
  '/v1/operations/position/p1/active': () => null,
};

const ARMS = {
  'quan-ly-tai-khoan': { path: '/admin/users', readyText: 'Trần Minh HM' },
  'chi-tiet-vi-tri': { path: '/positions/p1', readyText: 'REQ-2026-014' },
};

const measure = async (browser, arm) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    localStorage.setItem('hra_access_token', 'page-auth-me');
    localStorage.setItem('hra_locale', 'vi');
  });
  const unexpected = [];
  await context.route('**/v1/**', async route => {
    const url = new URL(route.request().url());
    const handler = RESPONSES[url.pathname];
    if (!handler) { unexpected.push(`${route.request().method()} ${url.pathname}`); return route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not mocked"}' }); }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(handler(url)) });
  });

  const page = await context.newPage();
  const gets = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/v1/')) gets.push({ method: request.method(), path: url.pathname });
  });

  await page.goto(`${base}${arm.path}`, { waitUntil: 'networkidle' });
  // Chốt chặn nội dung: danh tính phải tải xong, nếu không trang còn ở vòng
  // "Đang xác thực" và con số 0/1 chỉ là do chưa có gì chạy. Lọc `visible` vì
  // các màn còn giữ bản thẻ cho điện thoại (ẩn ở 1440px) với cùng chữ.
  await page.getByText(arm.readyText).filter({ visible: true }).first().waitFor({ timeout: 15000 });
  await page.waitForLoadState('networkidle');
  // Request thứ hai (nếu còn) bay cùng lượt với request đầu; đợi thêm để không
  // bỏ sót nó vì trang đã vẽ xong.
  await page.waitForTimeout(800);

  const authMe = gets.filter(request => request.path === AUTH_ME_PATH).length;
  const result = {
    path: arm.path,
    authMe,
    totalGet: gets.filter(request => request.method === 'GET').length,
    byPath: gets.reduce((acc, request) => ({ ...acc, [request.path]: (acc[request.path] || 0) + 1 }), {}),
    unexpected,
  };
  await context.close();
  return result;
};

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });

  const runs = {};
  for (const [name, arm] of Object.entries(ARMS)) {
    runs[name] = [];
    for (let index = 0; index < RUNS; index += 1) runs[name].push(await measure(browser, arm));
  }
  console.log(`PAGE_AUTH_ME ${JSON.stringify(runs)}`);

  for (const [name, [first]] of Object.entries(runs)) {
    const arm = ARMS[name];
    assert.deepEqual(first.unexpected, [], `${name} không được có request lạ: ${first.unexpected.join(', ')}`);
    assert.equal(first.byPath['/v1/positions/p1'] || 0, name === 'chi-tiet-vi-tri' ? 1 : 0, `${name}: kiểm tra đường tải vị trí`);
    // Đúng một request danh tính cho một lần mở trang; 0 nghĩa là đo hụt, 2 là
    // lỗi cũ quay lại (khung trang và trang tự hỏi riêng).
    for (const [index, run] of runs[name].entries()) {
      assert.equal(run.authMe, 1, `${name} lần ${index + 1}: mở trang chỉ được hỏi auth/me đúng một lần, thấy ${run.authMe}`);
    }
  }

  await browser.close();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
