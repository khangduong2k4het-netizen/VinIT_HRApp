import type { WorkQueueItem } from '@/types';
import { WORK_CONCEPT_LABELS } from './workVocabulary';

// Nhãn hiển thị của danh sách việc cần làm, tách khỏi component để test được
// mà không phải render React.

const TYPE_LABELS: Record<WorkQueueItem['type'], string> = {
  POSITION_SETUP: 'Thiết lập vị trí',
  CRITERIA_PENDING_HR: 'Tiêu chí chờ HR rà soát',
  CRITERIA_PENDING_HM: 'Tiêu chí chờ HM duyệt',
  // Cùng một việc thì cùng một tên với chip lọc ở trang xếp hạng.
  FILE_REVIEW: WORK_CONCEPT_LABELS.FILE_REVIEW,
  PROCESSING: 'Hồ sơ đang xử lý',
  NEEDS_VERIFICATION: WORK_CONCEPT_LABELS.NEEDS_VERIFICATION,
  DUPLICATE_PENDING: WORK_CONCEPT_LABELS.DUPLICATE,
  POSSIBLE_MISMATCH: WORK_CONCEPT_LABELS.POSSIBLE_MISMATCH,
  NOT_ASSESSED: WORK_CONCEPT_LABELS.NOT_ASSESSED,
  SHARE_WITHOUT_FEEDBACK: 'Shortlist chưa có phản hồi',
  POSITION_DEADLINE_PASSED: 'Vị trí đã quá hạn ứng tuyển',
  POSITION_DEADLINE_SOON: 'Vị trí sắp hết hạn ứng tuyển',
  INTERVIEW_TODAY: 'Buổi phỏng vấn hôm nay',
  SCORECARD_OVERDUE: 'Phiếu chấm đã quá hạn',
};

const TYPE_ACTIONS: Record<WorkQueueItem['type'], string> = {
  POSITION_SETUP: 'Tiếp tục thiết lập',
  CRITERIA_PENDING_HR: 'Rà soát tiêu chí',
  CRITERIA_PENDING_HM: 'Mở phê duyệt tiêu chí',
  FILE_REVIEW: 'Kiểm tra file',
  PROCESSING: 'Theo dõi xử lý',
  NEEDS_VERIFICATION: 'Xác minh hồ sơ',
  DUPLICATE_PENDING: 'Kiểm tra cảnh báo',
  POSSIBLE_MISMATCH: 'Mở hàng đợi rà soát',
  NOT_ASSESSED: 'Mở danh sách hồ sơ',
  SHARE_WITHOUT_FEEDBACK: 'Mở Shortlist',
  POSITION_DEADLINE_PASSED: 'Xem vị trí',
  POSITION_DEADLINE_SOON: 'Xem vị trí',
  INTERVIEW_TODAY: 'Mở lịch phỏng vấn',
  SCORECARD_OVERDUE: 'Chấm điểm',
};

/** Một loại việc mới từ backend chưa có trong bản build này không được hiện "undefined". */
export function workQueueTypeLabel(item: Pick<WorkQueueItem, 'type'>): string {
  return TYPE_LABELS[item.type] ?? 'Việc cần xử lý';
}

export function workQueueTypeAction(item: Pick<WorkQueueItem, 'type'>): string {
  return TYPE_ACTIONS[item.type] ?? 'Mở';
}

/** Số ngày còn lại thành câu; `null` khi việc không gắn với hạn chót. */
export function deadlineNote(
  item: Pick<WorkQueueItem, 'days_left'>,
  t: (key: string, ...args: Array<string | number>) => string,
): string | null {
  if (item.days_left == null) return null;
  if (item.days_left < 0) return t('Đã quá hạn {0} ngày', Math.abs(item.days_left));
  if (item.days_left === 0) return t('Hạn chót là hôm nay');
  return t('Còn {0} ngày tới hạn', item.days_left);
}
