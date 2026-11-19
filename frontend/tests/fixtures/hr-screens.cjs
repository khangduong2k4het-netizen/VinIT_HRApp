/**
 * One deterministic HR dataset, shared by the screenshot run and the UX metric
 * run so both describe the same screen. No live staging records are read.
 *
 * `workQueue()` mirrors `backend/app/services/workspace.py:summarize_applications`:
 * NOT_ASSESSED rows are counted as `not_assessed` and skipped before
 * `needs_verification`, which is the drift UX-R1 is about.
 */
const POSITION = {
  position_id: 'p1',
  position_code: 'REQ-2026-014',
  title: 'Senior Backend Engineer (Python)',
  status: 'OPEN',
  department_id: 'd1',
  department_name: 'Nền tảng & Hạ tầng',
  criteria_status: 'APPROVED',
};

// The approved rubric, as `GET /criteria/position/p1/approved` returns it. The
// assessment response only carries criterion names, so U2 reads the requirement
// text from here. c1 has description + spec, c2 has guidance, c3 has neither (so
// the card must not show an empty toggle), c4 has a JD reference only.
const RUBRIC = {
  criteria_version_id: 'cv1',
  position_id: 'p1',
  jd_version_id: 'jd1',
  version_number: 1,
  status: 'APPROVED',
  origin: 'HR_CREATED',
  mandatory_weight_total: 70,
  nice_to_have_weight_total: 30,
  criteria: [
    {
      criterion_id: 'c1',
      criteria_version_id: 'cv1',
      name: 'Kinh nghiệm Python cho dịch vụ production',
      description: 'Xây dựng và vận hành dịch vụ Python chạy thật, có tải production và số liệu độ trễ.',
      category: 'MUST_HAVE',
      weight_in_group: 60,
      expected_evidence_keywords: ['FastAPI', 'asyncio'],
      requirement_spec: { kind: 'YEARS', terms: ['FastAPI'], min_years: 3, required_languages: [], required_degree_level: null },
      evidence_guidance: 'Tên hệ thống, lưu lượng, p99 và vai trò cụ thể của ứng viên.',
      jd_reference_text: 'Production Python services with measurable latency',
      display_order: 1,
    },
    {
      criterion_id: 'c2',
      criteria_version_id: 'cv1',
      name: 'Thiết kế cơ sở dữ liệu quan hệ và tối ưu truy vấn',
      description: 'Thiết kế schema quan hệ và tối ưu truy vấn có số liệu trước/sau.',
      category: 'MUST_HAVE',
      weight_in_group: 40,
      expected_evidence_keywords: ['PostgreSQL', 'index'],
      requirement_spec: null,
      evidence_guidance: 'Số liệu thời gian truy vấn trước và sau khi tối ưu, không chỉ tên công nghệ.',
      jd_reference_text: null,
      display_order: 2,
    },
    {
      criterion_id: 'c3',
      criteria_version_id: 'cv1',
      name: 'Kinh nghiệm dẫn dắt nhóm kỹ thuật nhỏ',
      description: '',
      category: 'NICE_TO_HAVE',
      weight_in_group: 100,
      expected_evidence_keywords: [],
      requirement_spec: null,
      evidence_guidance: null,
      jd_reference_text: null,
      display_order: 3,
    },
  ],
};

const CRITERIA = [
  {
    result_id: 'r-c1', hr_reviews: [], criterion_id: 'c1', criterion_name: 'Kinh nghiệm Python cho dịch vụ production', category: 'MUST_HAVE',
    outcome: 'STRONG_MATCH', score: 92, confidence: 0.91, decision_source: 'HYBRID', evidence_strength: 0.88,
    requires_verification: false, page_number: 2,
    reasoning: 'Ứng viên mô tả 4 năm xây dịch vụ FastAPI cho 1.2 triệu request/ngày và nêu rõ cách xử lý backpressure.',
    verbatim_quote: 'Thiết kế lại luồng ingest bằng FastAPI + asyncio, xử lý 1.2 triệu request/ngày với p99 dưới 120ms.',
    evidence: [{ evidence_id: 'e1', verbatim_quote: 'Thiết kế lại luồng ingest bằng FastAPI + asyncio, xử lý 1.2 triệu request/ngày với p99 dưới 120ms.', page_number: 2, verification_status: 'VERIFIED' }],
  },
  {
    result_id: 'r-c2', hr_reviews: [], criterion_id: 'c2', criterion_name: 'Thiết kế cơ sở dữ liệu quan hệ và tối ưu truy vấn', category: 'MUST_HAVE',
    outcome: 'MATCH', score: 78, confidence: 0.72, decision_source: 'AI', evidence_strength: 0.64,
    requires_verification: true, page_number: 3,
    reasoning: 'Có nhắc tới PostgreSQL và index, nhưng chưa nêu số liệu trước/sau tối ưu nên chưa xác minh được mức độ.',
    verbatim_quote: 'Tối ưu truy vấn báo cáo trên PostgreSQL, thêm composite index cho bảng events.',
    evidence: [{ evidence_id: 'e2', verbatim_quote: 'Tối ưu truy vấn báo cáo trên PostgreSQL, thêm composite index cho bảng events.', page_number: 3, verification_status: 'UNVERIFIED' }],
  },
  {
    result_id: 'r-c3', hr_reviews: [], criterion_id: 'c3', criterion_name: 'Kinh nghiệm dẫn dắt nhóm kỹ thuật nhỏ', category: 'NICE_TO_HAVE',
    outcome: 'UNCLEAR', score: null, confidence: 0.4, decision_source: 'AI', evidence_strength: 0.31,
    requires_verification: true, page_number: null,
    reasoning: 'CV chỉ nêu vai trò "technical lead" mà không nói quy mô nhóm hay phạm vi trách nhiệm.',
    verbatim_quote: 'Technical lead cho mảng thanh toán nội bộ.',
    evidence: [{ evidence_id: 'e3', verbatim_quote: 'Technical lead cho mảng thanh toán nội bộ.', page_number: 4, verification_status: 'UNVERIFIED' }],
  },
  {
    result_id: 'r-c4', hr_reviews: [], criterion_id: 'c4', criterion_name: 'Kinh nghiệm vận hành Kubernetes trên cloud', category: 'NICE_TO_HAVE',
    outcome: 'NO_MATCH', score: 0, confidence: 0.83, decision_source: 'RULE', evidence_strength: 0.9,
    requires_verification: false, page_number: null,
    reasoning: 'Không tìm thấy từ khoá Kubernetes, EKS hay GKE trong CV.',
    verbatim_quote: null, evidence: [],
  },
];

const NAMES = [
  'Nguyễn Minh Anh', 'Trần Quốc Bảo', 'Lê Thu Hà', 'Phạm Đình Khang', 'Hoàng Mai Linh', 'Đỗ Văn Nam',
  'Vũ Thị Ngọc', 'Bùi Anh Tuấn', 'Ngô Thanh Tùng', 'Dương Hồng Yến', 'Lý Gia Hân', 'Phan Trọng Nghĩa',
];

const STATUSES = [
  'NEEDS_HR_VERIFICATION', 'MEETS_MANDATORY', 'NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH',
  'MEETS_MANDATORY', 'NEEDS_HR_VERIFICATION', 'MEETS_MANDATORY', 'NOT_ASSESSED',
  'NEEDS_HR_VERIFICATION', 'POSSIBLE_MISMATCH', 'MEETS_MANDATORY', 'NOT_ASSESSED',
];

const COVERAGES = [0.55, 0.92, 0.61, 0.78, 0.88, 0.49, 0.95, 0, 0.66, 0.74, 0.9, 0];
const SCORES = [72, 88, 69, 61, 83, 58, 91, null, 64, 67, 86, null];

const ranking = NAMES.map((name, index) => {
  const status = STATUSES[index];
  const coverage = COVERAGES[index];
  return {
    application_id: `app-${index}`,
    position_id: 'p1',
    candidate_name: name,
    rank_number: status === 'NOT_ASSESSED' || coverage < 0.7 ? null : index + 1,
    matching_status: status,
    matching_score: SCORES[index],
    evidence_coverage: coverage,
    ltr_score: null,
    needs_verification: status === 'NEEDS_HR_VERIFICATION' || (coverage > 0 && coverage < 0.7),
    has_mismatch: status === 'POSSIBLE_MISMATCH',
    criterion_results: CRITERIA.map(c => ({
      criterion_id: c.criterion_id, criterion_name: c.criterion_name, category: c.category,
      outcome: c.outcome, score: c.score, effective_weight: 30, requires_verification: c.requires_verification,
    })),
    file_processing_status: index === 5 ? 'NEEDS_HR_REVIEW' : index === 7 ? 'PROCESSING' : 'COMPLETED',
    file_error: index === 5 ? 'PDF có 3 trang scan không trích xuất được text.' : null,
    has_duplicate_warning: index === 3 || index === 9,
    is_shortlisted: index === 1 || index === 6,
    application_status: index === 1 || index === 6 ? 'SHORTLIST' : index === 11 ? 'NEW' : 'IN_REVIEW',
    created_at: `2026-10-${String(12 + index).padStart(2, '0')}T08:30:00Z`,
  };
});

const applications = ranking.map(item => ({
  application_id: item.application_id,
  position_id: 'p1',
  candidate_name: item.candidate_name,
  application_status: item.application_status,
  file_processing_status: item.file_processing_status,
  file_error: item.file_error,
  has_duplicate_warning: item.has_duplicate_warning,
  created_at: item.created_at,
  identity: { display_name: item.candidate_name },
}));

const inScreening = status => ['NEW', 'IN_REVIEW', 'SHORTLIST'].includes(status || '');
const visible = ranking.filter(item => inScreening(item.application_status));

const workQueueSummary = {
  positions_needing_attention: 2,
  files_needing_review: visible.filter(item => item.file_processing_status === 'NEEDS_HR_REVIEW').length,
  applications_needing_verification: visible.filter(item => item.matching_status !== 'NOT_ASSESSED'
    && (item.matching_status === 'NEEDS_HR_VERIFICATION' || item.evidence_coverage < 0.7)).length,
  // Mirrors the backend's verification_complete bucket: rows a reviewer finished
  // checking. Kept separate so the dashboard can show finished work instead of
  // only shrinking the pending number.
  applications_verification_complete: 3,
  duplicate_alerts: visible.filter(item => item.has_duplicate_warning).length,
  criteria_pending_action: 1,
  shares_without_feedback: 2,
};

const workQueue = {
  generated_at: '2026-11-19T03:00:00Z',
  summary: workQueueSummary,
  items: [
    { item_id: 'FILE_REVIEW:p1', type: 'FILE_REVIEW', priority: 'HIGH', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: workQueueSummary.files_needing_review, target: { pathname: '/positions/p1/applicants', search: 'queue=FILE_REVIEW' } },
    { item_id: 'NEEDS_VERIFICATION:p1', type: 'NEEDS_VERIFICATION', priority: 'HIGH', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: workQueueSummary.applications_needing_verification, target: { pathname: '/positions/p1/applicants', search: 'queue=NEEDS_VERIFICATION' } },
    { item_id: 'CRITERIA_PENDING_HM:p3', type: 'CRITERIA_PENDING_HM', priority: 'HIGH', position_id: 'p3', position_code: 'REQ-2026-021', position_title: 'Data Engineer', position_status: 'OPEN', count: 1, target: { pathname: '/positions/p3', search: 'tab=criteria' } },
    { item_id: 'DUPLICATE_PENDING:p1', type: 'DUPLICATE_PENDING', priority: 'MEDIUM', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: workQueueSummary.duplicate_alerts, target: { pathname: '/positions/p1/applicants', search: 'queue=DUPLICATE' } },
    { item_id: 'POSSIBLE_MISMATCH:p1', type: 'POSSIBLE_MISMATCH', priority: 'MEDIUM', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: visible.filter(item => item.matching_status === 'POSSIBLE_MISMATCH').length, target: { pathname: '/positions/p1/applicants', search: 'queue=POSSIBLE_MISMATCH' } },
    { item_id: 'NOT_ASSESSED:p1', type: 'NOT_ASSESSED', priority: 'MEDIUM', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: visible.filter(item => item.matching_status === 'NOT_ASSESSED').length, target: { pathname: '/positions/p1/applicants', search: 'queue=NOT_ASSESSED' } },
    { item_id: 'SHARE_WITHOUT_FEEDBACK:p1', type: 'SHARE_WITHOUT_FEEDBACK', priority: 'LOW', position_id: 'p1', position_code: POSITION.position_code, position_title: POSITION.title, position_status: 'OPEN', count: 2, target: { pathname: '/shortlist', search: '' } },
  ],
};

const dashboardSummary = {
  open_positions: 4,
  total_applications: 38,
  applications_by_status: {
    NEW: 6, IN_REVIEW: 14, SHORTLIST: 5, REJECTED_SCREENING: 7,
    INTERVIEW: 3, REJECTED_INTERVIEW: 2, OFFERED: 1, ACCEPTED: 0,
  },
  applications_processing: 2,
  // Same source as the work-queue summary above, so the card and the queue
  // subtitle cannot disagree in the screenshot.
  files_needing_hr_review: workQueueSummary.files_needing_review,
  files_needing_review: workQueueSummary.files_needing_review,
  files_needing_review_rate: 0.03,
  duplicate_alerts: workQueueSummary.duplicate_alerts,
  assessments_completed: 31,
  average_coverage: 0.74,
  coverage_sample_size: 31,
  coverage_under_threshold: 9,
};

const detail = {
  application_id: 'app-2',
  position_id: 'p1',
  source_code: 'CAREERS',
  application_status: 'IN_REVIEW',
  created_at: '2026-10-14T08:30:00Z',
  candidate_name: 'Lê Thu Hà',
  can_view_cv: true,
  can_update_status: true,
  can_manage_hr_notes: false,
  can_view_assessment_evidence: true,
  file_processing_status: 'COMPLETED',
  has_duplicate_warning: false,
  documents: [{ document_id: 'doc1', document_type: 'CV', original_filename: 'Le_Thu_Ha_CV_2026.pdf', mime_type: 'application/pdf', page_count: 4 }],
  identity: { display_name: 'Lê Thu Hà', email: 'le.thu.ha@example.com', phone: '09xx xxx 214' },
  latest_assessment: {
    assessment_id: 'a1',
    position_id: 'p1',
    application_id: 'app-2',
    matching_status: 'NEEDS_HR_VERIFICATION',
    matching_score: 69,
    evidence_coverage: 0.61,
    summary: 'Đáp ứng phần lớn yêu cầu bắt buộc; hai tiêu chí cần HR xác minh bằng chứng trước khi xếp hạng.',
    criterion_results: CRITERIA,
  },
};

const me = {
  user_id: 'u-hr', display_name: 'Nguyễn Thu Hằng', must_change_password: false,
  system_roles: ['HR_RECRUITER'], position_roles: ['HR_RECRUITER'],
  position_assignments: [
    { position_id: 'p1', position_role: 'HR_RECRUITER' },
    { position_id: 'p3', position_role: 'HR_RECRUITER' },
    { position_id: 'p4', position_role: 'HIRING_MANAGER' },
  ],
};

const statusEvents = [
  { event_id: 'ev1', previous_status: 'NEW', new_status: 'IN_REVIEW', reason: null, note: 'Bắt đầu rà soát bằng chứng.', changed_at: '2026-10-15T02:10:00Z', changed_by_name: 'Nguyễn Thu Hằng' },
];

const profile = {
  profile_version_id: 'pv1', version_number: 1,
  identity: { display_name: 'Lê Thu Hà', email: 'le.thu.ha@example.com', phone: '09xx xxx 214' },
  facts: [],
};

/**
 * Install the mock API on a Playwright context. `overrides` maps a path to a
 * handler so a test can change one answer (e.g. simulate a status change).
 */
function installMockApi(context, overrides = {}) {
  const unexpected = [];
  // A review recorded during the test must come back on the reload, otherwise the
  // test could pass on an optimistic UI that never actually persisted anything.
  const reviews = {};
  const route = async r => {
    const url = new URL(r.request().url());
    const p = url.pathname;
    if (overrides[p]) return overrides[p](r, url);
    const json = (body, status = 200) => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/v1/auth/me') return json(me);
    if (p === '/v1/dashboard/summary') return json(dashboardSummary);
    // The shortlist index calls this on mount. It was never mocked, so the page
    // got a 500 body and crashed with "Application error" — invisible to every
    // test that only walked the shortlist detail route.
    if (p === '/v1/shortlist/shared-with-me') return json([]);
    if (p === '/v1/dashboard/work-queue') return json(workQueue);
    if (p === '/v1/scorecards/reminders') return json([]);
    if (p === '/v1/positions' && r.request().method() === 'GET') return json([POSITION]);
    if (p === '/v1/positions/p1') return json(POSITION);
    if (p === '/v1/assessments/ranking/latest/p1') return json(ranking);
    if (p === '/v1/applications') return json(applications);
    if (p === '/v1/operations/position/p1/active') return json(null);
    if (p === '/v1/positions/p1/duplicate-signals') return json([]);
    if (p === '/v1/criteria/position/p1/approved') return json(RUBRIC);
    if (p === '/v1/shortlist/potential-recipients/p1') return json([]);
    if (p === '/v1/applications/app-2') {
      return json({
        ...detail,
        latest_assessment: {
          ...detail.latest_assessment,
          criterion_results: (detail.latest_assessment?.criterion_results || CRITERIA).map(c => ({
            ...c,
            hr_reviews: reviews[c.result_id] || [],
          })),
        },
      });
    }
    const reviewMatch = p.match(/^\/v1\/assessments\/results\/([^/]+)\/review$/);
    if (reviewMatch && r.request().method() === 'POST') {
      const body = JSON.parse(r.request().postData() || '{}');
      const resultId = reviewMatch[1];
      if (body.decision === 'REJECTED' && !(body.comment || '').trim()) {
        return json({ detail: 'Cần nêu lý do khi đánh dấu bằng chứng không đúng' }, 400);
      }
      const review = {
        review_id: `rev-${Object.keys(reviews).length + 1}`,
        decision: body.decision,
        comment: body.comment || null,
        reviewer_user_id: 'u-hr',
        reviewer_name: 'Nguyễn Thu Hằng',
        created_at: '2026-11-19T09:15:00Z',
      };
      // Append-only, like the table: a second look is a new row.
      reviews[resultId] = [review, ...(reviews[resultId] || [])];
      return r.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(review) });
    }
    if (p === '/v1/applications/app-2/status-events') return json(statusEvents);
    if (p === '/v1/applications/app-2/profile') return json(profile);
    if (p === '/v1/applications/app-2/cv-file') {
      return r.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n' });
    }
    // Any other application row from the ranking can be opened too: finishing a
    // profile advances to the next one, and that page must load in the mock.
    const applicationMatch = p.match(/^\/v1\/applications\/(app-\d+)$/);
    if (applicationMatch && r.request().method() === 'GET') {
      const id = applicationMatch[1];
      const row = ranking.find(item => item.application_id === id);
      return json({
        ...detail,
        application_id: id,
        candidate_name: row?.candidate_name || detail.candidate_name,
        identity: { ...detail.identity, display_name: row?.candidate_name || detail.identity.display_name },
        application_status: row?.application_status || detail.application_status,
        latest_assessment: {
          ...detail.latest_assessment,
          application_id: id,
          criterion_results: CRITERIA.map(c => ({ ...c, hr_reviews: reviews[c.result_id] || [] })),
        },
      });
    }
    const statusMatch = p.match(/^\/v1\/applications\/(app-\d+)\/status$/);
    if (statusMatch && r.request().method() === 'PATCH') {
      const body = JSON.parse(r.request().postData() || '{}');
      return json({ ...detail, application_id: statusMatch[1], application_status: body.new_status });
    }
    if (/^\/v1\/applications\/app-\d+\/(status-events|profile|cv-file)$/.test(p)) {
      if (p.endsWith('/status-events')) return json(statusEvents);
      if (p.endsWith('/profile')) return json(profile);
      return r.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n' });
    }
    unexpected.push(`${r.request().method()} ${p}${url.search}`);
    return json({});
  };
  return context.route('**/v1/**', route).then(() => unexpected);
}

module.exports = {
  POSITION, CRITERIA, RUBRIC, NAMES, ranking, applications, visible,
  workQueue, workQueueSummary, dashboardSummary, detail, me, profile,
  installMockApi,
};
