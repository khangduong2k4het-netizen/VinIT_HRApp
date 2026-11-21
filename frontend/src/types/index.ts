export interface JDVersion {
  jd_version_id: string;
  position_id: string;
  version_number: number;
  content_text: string;
  language_code: 'vi' | 'en';
  created_by: string;
  created_at: string;
}

export interface Department {
  department_id: string;
  name: string;
  code_format: string;
  next_sequence: number;
  is_active: boolean;
  position_count?: number;
  created_by?: string;
  created_at: string;
  updated_at?: string;
}

export interface Position {
  position_id: string;
  position_code: string;
  title: string;
  job_family?: string | null;
  job_family_id?: string | null;
  org_unit?: string;
  department_id?: string;
  department_name?: string;
  department_code_format?: string;
  department_sequence?: number;
  level?: string;
  work_location?: string;
  work_mode?: string;
  employment_type?: string;
  headcount?: number;
  status: 'OPEN' | 'PAUSED' | 'CLOSED';
  created_by: string;
  application_deadline_at?: string | null;
  opened_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at?: string;
  criteria_status?: 'DRAFT' | 'PENDING_HR_REVIEW' | 'PENDING_HM_APPROVAL' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED' | null;
  criteria_approved?: boolean;
}

export type WorkQueueItemType =
  | 'POSITION_SETUP'
  | 'CRITERIA_PENDING_HR'
  | 'CRITERIA_PENDING_HM'
  | 'FILE_REVIEW'
  | 'PROCESSING'
  | 'NEEDS_VERIFICATION'
  | 'DUPLICATE_PENDING'
  | 'POSSIBLE_MISMATCH'
  | 'NOT_ASSESSED'
  | 'SHARE_WITHOUT_FEEDBACK'
  | 'POSITION_DEADLINE_PASSED'
  | 'POSITION_DEADLINE_SOON';

export interface WorkQueueItem {
  item_id: string;
  type: WorkQueueItemType;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  position_id: string;
  position_code?: string;
  position_title?: string;
  position_status?: string;
  count: number;
  target: { pathname: string; search?: string };
  /**
   * Hồ sơ mà dòng việc này nên mở đầu tiên (hồ sơ chờ lâu nhất trong đúng nhóm
   * của nó). Có ở việc gắn với hồ sơ; vắng ở việc về vị trí, khi đó UI dùng
   * `target` như cũ.
   */
  next_application_id?: string | null;
  /** Hạn ứng tuyển của vị trí (chỉ có ở việc liên quan tới hạn). */
  due_at?: string;
  /** Số ngày còn lại tới hạn; âm nghĩa là đã quá hạn. */
  days_left?: number;
}

export interface WorkQueueResponse {
  generated_at: string;
  summary: {
    positions_needing_attention: number;
    files_needing_review: number;
    applications_needing_verification: number;
    /**
     * Applications whose flagged criteria have all been reviewed. Optional
     * because an older backend will not send it; the screen falls back to
     * showing the pending figure alone rather than a wrong fraction.
     */
    applications_verification_complete?: number;
    duplicate_alerts: number;
    criteria_pending_action: number;
    shares_without_feedback: number;
    positions_deadline_passed?: number;
    positions_deadline_soon?: number;
    applications_waiting_over_threshold?: number;
    /** Ngưỡng đang áp dụng (HR đổi được trong Cài đặt HR). */
    deadline_soon_days?: number;
    waiting_attention_days?: number;
    /** null khi chưa có hồ sơ nào có mốc thời gian — không phải 0. */
    oldest_waiting_days?: number | null;
    median_waiting_days?: number | null;
  };
  items: WorkQueueItem[];
}

export type WorkflowStepCode = 'JD' | 'CRITERIA' | 'CV_INTAKE' | 'HR_REVIEW' | 'SHORTLIST';
export type WorkflowStepStatus = 'COMPLETED' | 'CURRENT' | 'NOT_STARTED' | 'BLOCKED';

export interface PositionWorkspace {
  position: {
    position_id: string;
    position_code?: string;
    title?: string;
    status?: string;
    department_name?: string;
  };
  jd: { latest_version_id: string | null; version_number?: number | null };
  criteria: {
    current_version_id: string | null;
    current_status: string | null;
    version_number?: number | null;
    approved_for_latest_jd: boolean;
    is_stale_for_latest_jd: boolean;
  };
  counts: {
    total: number;
    assessed: number;
    processing: number;
    file_review: number;
    not_assessed: number;
    needs_verification: number;
    possible_mismatch: number;
    meets_mandatory: number;
    duplicate_pending: number;
    shortlisted: number;
  };
  active_operation: { operation_id: string; status?: string; stage?: string } | null;
  workflow: {
    current_step: WorkflowStepCode;
    steps: Array<{ code: WorkflowStepCode; status: WorkflowStepStatus }>;
    next_action: {
      code: string;
      blocked_reason_code: string | null;
      target: { pathname: string; search?: string };
    };
  };
  viewer: {
    is_hr: boolean;
    is_hm: boolean;
    position_roles: string[];
    system_roles: string[];
  };
}

export interface OperationProgress {
  total: number;
  processed: number;
  failed: number;
  percent_complete: number;
  /** `application_id` is present when the rejected file still created a profile. */
  invalid_files?: Array<{ original_filename: string; error_code?: string; application_id?: string | null }>;
}

export interface OperationStatus {
  operation_id: string;
  status?: string;
  stage?: string;
  capability?: string;
  progress?: OperationProgress;
  error_message?: string;
}

export interface RequirementSpec {
  kind: 'SKILL' | 'YEARS' | 'DEGREE' | 'CERTIFICATION' | 'LANGUAGE';
  terms: string[];
  min_years?: number | null;
  required_degree_level?: number | null;
  required_languages: string[];
  required_ielts?: number | null;
  required_toeic?: number | null;
  required_cefr?: 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2' | null;
  required_language_rank?: number | null;
}

export interface Criterion {
  criterion_id: string;
  criteria_version_id: string;
  name: string;
  description: string;
  category: 'MUST_HAVE' | 'NICE_TO_HAVE';
  weight_in_group: number;
  expected_evidence_keywords: string[];
  requirement_spec?: RequirementSpec | null;
  evidence_guidance?: string;
  jd_reference_text?: string;
  display_order: number;
}

export interface CriteriaVersion {
  criteria_version_id: string;
  position_id: string;
  jd_version_id: string;
  version_number: number;
  origin: 'AI_DRAFT' | 'HR_CREATED' | 'TEMPLATE_CLONE';
  source_template_version_id?: string | null;
  // SUPERSEDED = từng duyệt và đang dùng, sau đó bị một bộ mới hơn thay thế
  // (migration 00037). Nó là bằng chứng lịch sử, KHÔNG phải bộ đang hiệu lực.
  status: 'DRAFT' | 'PENDING_HR_REVIEW' | 'PENDING_HM_APPROVAL' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED';
  mandatory_weight_total: number;
  nice_to_have_weight_total: number;
  approved_by_hr?: string;
  approved_by_hm?: string;
  approved_by_hr_at?: string;
  approved_by_hm_at?: string;
  created_at: string;
  criteria: Criterion[];
}

export interface Application {
  application_id: string;
  position_id: string;
  source_code: string;
  application_status: string;
  created_at: string;
  updated_at?: string;
}

export interface RankingCriterionResult {
  criterion_id: string;
  criterion_name: string;
  category: string;
  outcome: 'STRONG_MATCH' | 'MATCH' | 'UNCLEAR' | 'NO_MATCH';
  score: number | null;
  effective_weight: number | null;
  requires_verification: boolean;
}

export interface RankingItem {
  rank_number: number | null;
  application_id: string;
  candidate_name: string;
  matching_status: 'NOT_ASSESSED' | 'NEEDS_HR_VERIFICATION' | 'POSSIBLE_MISMATCH' | 'MEETS_MANDATORY';
  matching_score: number | null;
  evidence_coverage: number | null;
  ltr_score?: number | null;
  needs_verification: boolean;
  has_mismatch: boolean;
  criterion_results?: RankingCriterionResult[];
  file_processing_status?: 'COMPLETED' | 'PROCESSING' | 'NEEDS_HR_REVIEW' | 'UNKNOWN';
  file_error?: string;
  has_duplicate_warning?: boolean;
  is_shortlisted?: boolean;
  application_status?: string;
  created_at?: string;
  /** HR đang giữ hồ sơ; vắng mặt nghĩa là chưa ai nhận. */
  assigned_to?: string | null;
  assigned_to_name?: string | null;
}

export interface UserSummary {
  user_id: string;
  display_name: string;
  position_roles?: string[];
  system_roles?: string[];
}

export interface PrivateNote {
  note_id: string;
  content: string;
  /** null = ghi chú chung của hồ sơ; có id = ghi chú cho đúng tiêu chí đó. */
  criterion_id?: string | null;
  created_at: string;
  created_by?: string;
  author_name?: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  verbatim_quote: string;
  page_number: number | null;
  verification_status: string | null;
}

export interface HrCriterionReview {
  review_id: string;
  decision: 'CONFIRMED' | 'REJECTED';
  comment?: string | null;
  reviewer_user_id: string;
  reviewer_name?: string | null;
  created_at: string;
}

export interface CriterionResult {
  // Present on GET /assessments/{id}; the review endpoint needs it.
  result_id?: string;
  hr_reviews?: HrCriterionReview[];
  criterion_id: string;
  criterion_name: string;
  category: string;
  outcome: 'STRONG_MATCH' | 'MATCH' | 'UNCLEAR' | 'NO_MATCH';
  score: number | null;
  confidence: number | null;
  reasoning: string | null;
  requires_verification: boolean;
  decision_source?: 'RULE' | 'LLM' | 'HYBRID' | null;
  evidence_strength?: number | null;
  evidence_chunk_id?: string | null;
  rule_version?: string | null;
  verbatim_quote?: string;
  page_number?: number;
  evidence?: EvidenceItem[];
}

export interface ApplicationWithAssessment {
  application_id: string;
  position_id: string;
  source_code: string;
  application_status: string;
  created_at: string;
  updated_at?: string;
  candidate_name?: string;
  matching_status?: string;
  matching_score?: number | null;
  evidence_coverage?: number | null;
  identity?: {
    display_name?: string;
    email?: string;
    phone?: string;
  };
  latest_assessment?: AssessmentDetail | null;
  file_processing_status?: 'COMPLETED' | 'PROCESSING' | 'NEEDS_HR_REVIEW' | 'UNKNOWN';
  file_error?: string | null;
  has_duplicate_warning?: boolean;
  can_view_cv?: boolean;
  can_view_assessment_evidence?: boolean;
  can_update_status?: boolean;
  can_manage_hr_notes?: boolean;
  /** HR đang phụ trách hồ sơ này; null/undefined = chưa ai nhận. */
  assigned_to?: string | null;
  assigned_to_name?: string | null;
  assigned_at?: string | null;
  /** Every action the profile screen may offer; see lib/applicationCapabilities.ts. */
  capabilities?: {
    view_cv?: boolean;
    view_evidence?: boolean;
    update_status?: boolean;
    review_evidence?: boolean;
    manage_hr_notes?: boolean;
    edit_profile?: boolean;
    view_status_history?: boolean;
    reprocess_cv?: boolean;
  };
  documents?: Array<{
    document_id: string;
    document_type: string;
    original_filename: string;
    mime_type?: string;
    page_count?: number;
    /** 'UNSCANNED' khi tệp vào hệ thống lúc máy quét virus không chạy. */
    scan_state?: 'SCANNED' | 'UNSCANNED' | 'INFECTED';
  }>;
}

export interface AssessmentDetail {
  assessment_id: string;
  position_id: string;
  application_id: string;
  matching_status: string;
  matching_score: number | null;
  evidence_coverage: number | null;
  summary: string | null;
  assessment_fingerprint?: string | null;
  matching_policy_version?: string | null;
  prompt_version?: string | null;
  criterion_results: CriterionResult[];
}

export interface RosterItem {
  roster_id: string;
  position_id: string;
  application_id: string;
  candidate_name: string;
  matching_score: number;
  roster_status: string;
  added_at: string;
  recommended_decision: string;
  hm_notes?: string;
}


