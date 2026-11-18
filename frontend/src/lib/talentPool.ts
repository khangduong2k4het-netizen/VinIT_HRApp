// P3-1 Talent Pool: labels shared by the applicant panel, the pool list and the scan page.

export const POOL_REASONS: Record<string, string> = {
  STRONG_FIT: 'Phù hợp tốt, chưa có vị trí',
  NEAR_MISS: 'Sát vòng cuối',
  OTHER_ROLE_FIT: 'Hợp vị trí khác',
};

export const MATCHING_STATUS_LABELS: Record<string, { label: string; color: 'success' | 'warning' | 'error' | 'default' }> = {
  MEETS_MANDATORY: { label: 'Đáp ứng bắt buộc', color: 'success' },
  NEEDS_HR_VERIFICATION: { label: 'Cần HR xác minh', color: 'warning' },
  POSSIBLE_MISMATCH: { label: 'Có dấu hiệu chưa đáp ứng', color: 'error' },
  NOT_ASSESSED: { label: 'Chưa đánh giá', color: 'default' },
};

export const SCAN_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Đang chờ xử lý',
  PROCESSING: 'Đang quét',
  COMPLETED: 'Đã quét xong',
  FAILED: 'Quét thất bại',
};

export type PoolState = {
  marked: boolean; can_mark: boolean; reason: string | null; reason_text: string | null; expires_on: string | null;
};

export type ScanCriterion = { criterion_id: string; name: string | null; category: string | null; outcome: string | null; quote: string | null };

export type ScanResult = {
  application_id: string; status: 'SCORED' | 'FAILED'; rank_number: number | null;
  matching_status: string | null; matching_score: number | null; evidence_coverage: number | null;
  criteria: ScanCriterion[]; candidate_name: string | null; email: string | null; phone: string | null;
  reason_code: string | null; source_position_code: string; source_position_title: string; source_application_status: string;
};

export type Scan = {
  scan_id: string; status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'; candidate_count: number;
  scored_count: number; failed_count: number; error_message: string | null; created_at: string; completed_at: string | null;
};
