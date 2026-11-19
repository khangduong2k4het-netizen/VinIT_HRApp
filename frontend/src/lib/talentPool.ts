// P3-1 Talent Pool: types and pure helpers (no React, so they can be unit tested).

export type PoolMark = {
  application_id: string; reason_code: string; marked_at: string; position_id: string;
  position_title: string; position_code: string; application_status: string; eligible: boolean; expires_on: string | null;
};
export type CriterionResult = { criterion_id: string; name: string | null; category: string | null; outcome: string; quote: string | null };
export type ScanResult = {
  rank: number; application_id: string; matching_score: number | null; evidence_coverage: number; matching_status: string;
  unresolved_count: number; criterion_results: CriterionResult[]; hr_decision: 'CONTACT' | 'SKIP' | 'LATER' | null;
  source_position_id: string; source_position_title: string; source_position_code: string; mark_reason: string | null;
  pool_expires_on: string;
};
export type ScanStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
export type ScanSummary = {
  scan_id: string; created_at: string; eligible_count: number; scored_count: number; skipped_counts: Record<string, number>;
  status: ScanStatus; failed_count: number; error_message: string | null; completed_at: string | null;
};
export type ScanDetail = ScanSummary & { position_id: string; results: ScanResult[] };

export const MARK_REASONS: Record<string, string> = {
  STRONG_FIT: 'Phù hợp tốt',
  NEAR_MISS: 'Suýt đạt',
  OTHER_ROLE_FIT: 'Hợp vị trí khác',
};
export const DECISIONS: Record<string, string> = { CONTACT: 'Liên hệ', LATER: 'Để sau', SKIP: 'Bỏ qua' };
export const OUTCOMES: Record<string, string> = {
  STRONG_MATCH: 'Đáp ứng tốt', MATCH: 'Đáp ứng', NO_MATCH: 'Chưa đáp ứng', UNCLEAR: 'Chưa rõ',
};
export const SKIP_REASONS: Record<string, string> = {
  NO_EXTRACTED_TEXT: 'Chưa có văn bản CV', TEXT_UNAVAILABLE: 'Không đọc được văn bản CV', OVER_LIMIT: 'Vượt giới hạn một lượt quét',
  ALREADY_APPLIED: 'Ứng viên đã ứng tuyển vị trí này', DUPLICATE_EMAIL: 'Trùng email, giữ hồ sơ tốt nhất', SCORING_ERROR: 'Lỗi khi chấm CV',
};

/** Short, non-identifying label for a pool application (no names are ever shown). */
export function poolRef(applicationId: string): string {
  return `#${applicationId.replace(/-/g, '').slice(0, 8).toUpperCase()}`;
}

export function scoreText(score: number | null): string {
  return score == null ? '—' : `${Math.round(score * 10) / 10}%`;
}

/** A scan the worker has not finished: the page keeps polling while this is true. */
export const scanIsActive = (status?: ScanStatus | null): boolean => status === 'PENDING' || status === 'PROCESSING';
