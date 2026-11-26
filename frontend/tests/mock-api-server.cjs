/**
 * Mock API cho việc XEM giao diện (không phải test tự động).
 *
 * Next.js đã proxy `/v1/*` sang `API_INTERNAL_URL` (mặc định
 * http://127.0.0.1:8000), nên chỉ cần chạy file này ở cổng đó rồi mở frontend:
 *
 *   node tests/mock-api-server.cjs          # 127.0.0.1:8000
 *   npm run build && npm run start          # frontend ở 127.0.0.1:3000
 *
 * Dữ liệu lấy từ `tests/fixtures/hr-screens.cjs` để màn hình xem được trùng với
 * dữ liệu của các test mock. Khác fixture gốc ở hai chỗ, có chủ ý:
 *
 *  - Bộ tiêu chí để `PENDING_HR_REVIEW` thay vì `APPROVED`, để thẻ duyệt ở đầu
 *    tab tiêu chí hiện ra (đó là thứ cần nhìn).
 *  - Bổ sung nhóm vị trí và hạn ứng tuyển cho POSITION, vì fixture gốc không có.
 */
const http = require('node:http');
const {
  POSITION, RUBRIC, ranking, applications, me, workQueue, dashboardSummary,
} = require('./fixtures/hr-screens.cjs');

const PORT = Number(process.argv[2] || process.env.MOCK_API_PORT || 8000);

const position = {
  ...POSITION,
  job_family_id: 'f1',
  job_family: 'IT & Digital',
  application_deadline_at: '2026-12-05T17:00:00Z',
  created_by: 'u-hr',
  created_at: '2026-10-01T08:00:00Z',
};

const jdV1 = {
  jd_version_id: 'jd1',
  position_id: 'p1',
  version_number: 1,
  language_code: 'vi',
  created_at: '2026-10-01T08:05:00Z',
  content_text: [
    'Senior Backend Engineer (Python) — Nền tảng & Hạ tầng',
    '',
    'Trách nhiệm:',
    '- Thiết kế, vận hành dịch vụ Python (FastAPI) chạy production, có số liệu độ trễ.',
    '- Thiết kế schema PostgreSQL và tối ưu truy vấn báo cáo.',
    '- Dẫn dắt nhóm 3-5 kỹ sư, review thiết kế và mentoring.',
    '',
    'Yêu cầu:',
    '- 3+ năm Python cho dịch vụ production.',
    '- Kinh nghiệm Kubernetes trên cloud là lợi thế.',
    '- Tiếng Anh đọc hiểu tài liệu kỹ thuật.',
  ].join('\n'),
};

// Cùng một bộ tiêu chí với fixture, chỉ đổi trạng thái để thấy được thẻ duyệt.
const criteriaV1 = { ...RUBRIC, status: 'PENDING_HR_REVIEW', approved_by_hr: null };

const counts = {
  total: 12,
  assessed: 10,
  processing: 1,
  file_review: 1,
  not_assessed: 2,
  needs_verification: 4,
  possible_mismatch: 2,
  meets_mandatory: 4,
  duplicate_pending: 2,
  shortlisted: 2,
};

const workspace = {
  position: {
    position_id: 'p1',
    position_code: position.position_code,
    title: position.title,
    status: position.status,
    department_name: position.department_name,
  },
  jd: { latest_version_id: 'jd1', version_number: 1 },
  criteria: {
    current_version_id: 'cv1',
    current_status: 'PENDING_HR_REVIEW',
    version_number: 1,
    approved_for_latest_jd: false,
    is_stale_for_latest_jd: false,
  },
  counts,
  active_operation: null,
  workflow: {
    current_step: 'CRITERIA',
    steps: [
      { code: 'JD', status: 'COMPLETED' },
      { code: 'CRITERIA', status: 'CURRENT' },
      { code: 'CV_INTAKE', status: 'NOT_STARTED' },
      { code: 'HR_REVIEW', status: 'NOT_STARTED' },
      { code: 'SHORTLIST', status: 'NOT_STARTED' },
    ],
    next_action: {
      code: 'REVIEW_CRITERIA_HR',
      blocked_reason_code: null,
      target: { pathname: '/positions/p1', search: 'tab=criteria' },
    },
  },
  viewer: {
    is_hr: true,
    is_hm: false,
    position_roles: ['HR_RECRUITER'],
    system_roles: ['HR_RECRUITER'],
  },
};

const positionStats = {
  position_id: 'p1',
  position_title: position.title,
  total_applications: counts.total,
  applications_processing: counts.processing,
  files_needing_hr_review: counts.file_review,
  applications_by_status: { NEW: 2, IN_REVIEW: 6, SHORTLIST: 2, REJECTED_SCREENING: 2 },
};

const families = [
  { job_family_id: 'f1', code: 'IT_DIGITAL', name: 'IT & Digital' },
  { job_family_id: 'f2', code: 'ADMIN_OPERATIONS', name: 'Vận hành & Hành chính' },
];

function routes(path, method) {
  if (path === '/v1/auth/me') return me;
  if (path === '/v1/positions/p1') return position;
  if (path === '/v1/positions/p1/jd-versions') return [jdV1];
  if (path === '/v1/positions/p1/workspace') return workspace;
  if (path === '/v1/positions/p1/hiring-managers') return [];
  if (path === '/v1/positions/p1/duplicate-signals') return [];
  if (path === '/v1/criteria/position/p1/versions') return [criteriaV1];
  if (path === '/v1/criteria/position/p1/approved') return criteriaV1;
  if (path === '/v1/criteria/cv1/approval-events') return [];
  if (path === '/v1/dashboard/position/p1') return positionStats;
  if (path === '/v1/dashboard/work-queue') return workQueue;
  if (path === '/v1/dashboard/summary') return dashboardSummary;
  if (path === '/v1/operations/position/p1/active') return null;
  if (path === '/v1/rubric-library/families') return families;
  if (path === '/v1/rubric-library/templates') return [];
  if (path === '/v1/shortlist/shared-with-me') return [];
  if (path === '/v1/scorecards/reminders') return [];
  if (path === '/v1/applications') return applications;
  if (path === '/v1/assessments/ranking/latest/p1') return ranking;
  if (method === 'POST' || method === 'PATCH' || method === 'PUT') return { ok: true };
  return {};
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  const body = JSON.stringify(routes(url.pathname, req.method));
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(body);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`mock api on http://127.0.0.1:${PORT} (positions/p1, 12 hồ sơ)`);
});
