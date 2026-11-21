import { inScreening } from './applicantReview';
import type { RankingItem } from '@/types';

/**
 * Duyệt một tiêu chí trên nhiều hồ sơ.
 *
 * Việc thật của HR khi một tiêu chí bị nghi ngờ là đọc cùng một trích dẫn trên
 * vài chục CV rồi quyết định từng hồ sơ — không phải mở hồ sơ A, cuộn tới tiêu
 * chí đó, quay lại, mở hồ sơ B. Ranking đã trả sẵn kết quả từng tiêu chí cho
 * mọi hồ sơ trong một request, nên danh sách dựng được ngay; phần trích dẫn và
 * trạng thái "đã kiểm" cần dữ liệu chi tiết của từng hồ sơ, tải theo trang.
 */
export interface CriterionQueueRow {
  applicationId: string;
  candidateName: string;
  rankNumber: number | null;
  applicationStatus: string | null;
  matchingScore: number | null;
  evidenceCoverage: number | null;
  outcome: string | null;
  score: number | null;
  requiresVerification: boolean;
}

/**
 * Các dòng của một tiêu chí, theo đúng thứ tự xếp hạng. Hồ sơ chưa có kết quả
 * cho tiêu chí này (rubric cũ, chưa đánh giá) không phải việc của màn này nên
 * không hiện ra.
 */
export function buildCriterionRows(ranking: RankingItem[], criterionId: string): CriterionQueueRow[] {
  return ranking
    .filter(item => inScreening(item.application_status))
    .map(item => {
      const result = (item.criterion_results || []).find(entry => entry.criterion_id === criterionId);
      return {
        applicationId: item.application_id,
        candidateName: item.candidate_name,
        rankNumber: item.rank_number,
        applicationStatus: item.application_status || null,
        matchingScore: item.matching_score,
        evidenceCoverage: item.evidence_coverage,
        outcome: result?.outcome || null,
        score: result?.score ?? null,
        requiresVerification: Boolean(result?.requires_verification),
      };
    })
    .filter(row => row.outcome !== null);
}

/**
 * Một dòng đang ở trạng thái nào. Chỉ `PENDING` mới được ghi nhận xác minh:
 * tiêu chí không bị gắn cờ thì không có gì để xác nhận, và hồ sơ đã kiểm rồi
 * thì lần bấm thứ hai không được tạo thêm một bản ghi nữa.
 */
export type CriterionRowState = 'LOADING' | 'PENDING' | 'REVIEWED' | 'NOT_REQUIRED' | 'NO_RESULT' | 'NO_PERMISSION';

export interface CriterionRowStateInput {
  /** Đã tải chi tiết hồ sơ (có trích dẫn, result_id, lần kiểm trước) chưa. */
  loaded: boolean;
  requiresVerification: boolean;
  hasResultId: boolean;
  reviewedDecision: 'CONFIRMED' | 'REJECTED' | null;
  canReview: boolean;
}

export function criterionRowState(input: CriterionRowStateInput): CriterionRowState {
  if (!input.loaded) return 'LOADING';
  if (!input.requiresVerification) return 'NOT_REQUIRED';
  if (!input.hasResultId) return 'NO_RESULT';
  if (input.reviewedDecision) return 'REVIEWED';
  if (!input.canReview) return 'NO_PERMISSION';
  return 'PENDING';
}

export function countCriterionProgress(rows: CriterionQueueRow[], stateOf: (row: CriterionQueueRow) => CriterionRowState) {
  return {
    flagged: rows.filter(row => row.requiresVerification).length,
    verified: rows.filter(row => stateOf(row) === 'REVIEWED').length,
  };
}
