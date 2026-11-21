import type { ApplicationStatus } from './applicationStatus';

/**
 * Trạng thái nên chọn sẵn khi HR mở hộp thoại hoàn tất hồ sơ.
 *
 * Hộp thoại cũ luôn mở ở "Giữ nguyên trạng thái", nên HR phải tự mở ô chọn rồi
 * tự suy ra bước tiếp theo — trong khi hồ sơ đã có đủ dữ liệu để nói bước đó.
 * Đề xuất ở đây chỉ là giá trị chọn sẵn: HR vẫn thấy nó trong ô chọn, đổi được,
 * và vẫn phải bấm nút hoàn tất. Không có bước nào tự chạy.
 *
 * Quy tắc, theo thứ tự ưu tiên:
 *  1. Có tiêu chí bắt buộc chưa đạt → loại ở vòng sàng lọc (lý do vẫn do HR nhập).
 *  2. Hồ sơ còn ở "Mới" → chuyển sang "Đang xem": bắt đầu xem là bước tự nhiên.
 *  3. Đang xem và điểm tổng hợp đạt ngưỡng → Shortlist.
 *  4. Đã shortlist → phỏng vấn.
 *  5. Còn lại: giữ nguyên trạng thái, và hộp thoại không nói gì thêm.
 */
export type FinishSuggestionReason = 'NONE' | 'MANDATORY_FAILED' | 'START_REVIEW' | 'READY_FOR_SHORTLIST' | 'ADVANCE_STAGE';

export interface FinishSuggestionInput {
  currentStatus: ApplicationStatus | null;
  /** Các bước chuyển hợp lệ mà backend cho phép từ trạng thái hiện tại. */
  nextStatuses: ApplicationStatus[];
  /** Có tiêu chí bắt buộc nào kết luận "chưa đáp ứng" hay không. */
  mandatoryFailed: boolean;
  score: number | null;
}

export interface FinishSuggestion {
  /** '' nghĩa là giữ nguyên trạng thái. */
  status: '' | ApplicationStatus;
  reason: FinishSuggestionReason;
}

/** Điểm tổng hợp dưới ngưỡng này thì đề xuất shortlist là đề xuất ẩu. */
export const SHORTLIST_MIN_SCORE = 60;

export function suggestFinishStatus({ currentStatus, nextStatuses, mandatoryFailed, score }: FinishSuggestionInput): FinishSuggestion {
  if (!currentStatus || nextStatuses.length === 0) return { status: '', reason: 'NONE' };
  if (mandatoryFailed && nextStatuses.includes('REJECTED_SCREENING')) {
    return { status: 'REJECTED_SCREENING', reason: 'MANDATORY_FAILED' };
  }
  if (currentStatus === 'NEW' && nextStatuses.includes('IN_REVIEW')) {
    return { status: 'IN_REVIEW', reason: 'START_REVIEW' };
  }
  if (currentStatus === 'IN_REVIEW' && nextStatuses.includes('SHORTLIST') && score !== null && score >= SHORTLIST_MIN_SCORE) {
    return { status: 'SHORTLIST', reason: 'READY_FOR_SHORTLIST' };
  }
  if (currentStatus === 'SHORTLIST' && nextStatuses.includes('INTERVIEW')) {
    return { status: 'INTERVIEW', reason: 'ADVANCE_STAGE' };
  }
  return { status: '', reason: 'NONE' };
}
