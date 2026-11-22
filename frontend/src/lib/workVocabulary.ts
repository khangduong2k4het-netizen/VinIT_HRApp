import type { ApplicantQueue } from '@/lib/applicantReview';
import type { WorkQueueItem } from '@/types';

/**
 * Một bộ từ vựng cho cả hai nơi HR làm việc: hàng đợi trên Dashboard và các
 * chip lọc ở trang xếp hạng. Trước đây hai hệ gọi cùng một việc bằng hai tên
 * khác nhau ("File CV cần HR kiểm tra" / "Cần kiểm tra file"), nên HR phải học
 * lại từ vựng khi đổi màn hình.
 *
 * Ba cụm phản ánh việc HR thực sự phải làm:
 *  - Cần tôi xử lý: việc còn thiếu dữ liệu hoặc cần kiểm tra.
 *  - Cần tôi quyết: đủ dữ kiện, đang chờ quyết định của HR/HM.
 *  - Đã quyết: quyết định đã ghi nhận.
 */
export type WorkCluster = 'ACTION' | 'DECISION' | 'DONE';

export const WORK_CLUSTERS: WorkCluster[] = ['ACTION', 'DECISION', 'DONE'];

export const WORK_CLUSTER_LABELS: Record<WorkCluster, string> = {
  ACTION: 'Cần tôi xử lý',
  DECISION: 'Cần tôi quyết',
  DONE: 'Đã quyết',
};

/** Nhãn dùng chung, không phụ thuộc màn hình nào. */
export const WORK_CONCEPT_LABELS = {
  FILE_REVIEW: 'Cần kiểm tra file',
  DUPLICATE: 'Cảnh báo trùng',
  NEEDS_VERIFICATION: 'Cần xác minh',
  POSSIBLE_MISMATCH: 'Có dấu hiệu chưa đáp ứng',
  NOT_ASSESSED: 'Chưa đánh giá',
  MEETS_MANDATORY: 'Đáp ứng bắt buộc',
  SHORTLIST: 'Đã shortlist',
} as const;

const ITEM_CLUSTERS: Record<WorkQueueItem['type'], WorkCluster> = {
  POSITION_SETUP: 'ACTION',
  CRITERIA_PENDING_HR: 'ACTION',
  CRITERIA_PENDING_HM: 'DECISION',
  FILE_REVIEW: 'ACTION',
  PROCESSING: 'ACTION',
  NEEDS_VERIFICATION: 'ACTION',
  DUPLICATE_PENDING: 'ACTION',
  POSSIBLE_MISMATCH: 'ACTION',
  NOT_ASSESSED: 'ACTION',
  SHARE_WITHOUT_FEEDBACK: 'DECISION',
  POSITION_DEADLINE_PASSED: 'ACTION',
  POSITION_DEADLINE_SOON: 'ACTION',
  // Hai loại này không đi qua `WorkQueueList` (chúng là việc của người dùng,
  // không của vị trí), nhưng kiểu Record bắt buộc phải khai đủ. Thiếu hai dòng
  // này là lỗi biên dịch, không phải lỗi hiển thị — nên cứ để kiểu ép khai.
  INTERVIEW_TODAY: 'ACTION',
  SCORECARD_OVERDUE: 'ACTION',
};

/** A work-queue type this build does not know lands in the actionable group. */
export function workQueueItemCluster(type: WorkQueueItem['type']): WorkCluster {
  return ITEM_CLUSTERS[type] ?? 'ACTION';
}

const QUEUE_CLUSTERS: Record<ApplicantQueue, WorkCluster | null> = {
  ALL: null,
  FILE_REVIEW: 'ACTION',
  DUPLICATE: 'ACTION',
  NEEDS_VERIFICATION: 'ACTION',
  POSSIBLE_MISMATCH: 'ACTION',
  NOT_ASSESSED: 'ACTION',
  MEETS_MANDATORY: 'DECISION',
  SHORTLIST: 'DONE',
};

/** `null` = the unfiltered view, which belongs to no cluster. */
export function applicantQueueCluster(queue: ApplicantQueue): WorkCluster | null {
  return QUEUE_CLUSTERS[queue] ?? null;
}
