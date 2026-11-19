/**
 * Hàng đợi lưu trữ/xoá dữ liệu theo từng hồ sơ.
 *
 * Backend cố ý không xoá tự động: một trường hợp chỉ được tạo sau khi vị trí đã
 * đóng và quá thời hạn lưu trữ, rồi phải được người có quyền xác nhận. Màn hình
 * chỉ được mời những hành động mà máy chủ sẽ chấp nhận, để HR không bấm rồi ăn 409.
 */
export interface RetentionCase {
  retention_case_id: string;
  application_id: string | null;
  application_opaque_id: string | null;
  position_id: string | null;
  policy_version: string | null;
  position_closed_at: string | null;
  due_date: string | null;
  status: string;
  execution_status: string | null;
  execution_in_progress_or_recovery: boolean;
  is_due: boolean;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string | null;
}

export const RETENTION_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Chờ xác nhận',
  SCHEDULED_FOR_DELETION: 'Đã lên lịch xoá',
  DELETED: 'Đã xoá dữ liệu',
  CANCELLED: 'Đã huỷ',
};

export const RETENTION_STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  PENDING: { bg: '#FFFAEB', color: '#B54708' },
  SCHEDULED_FOR_DELETION: { bg: '#EFF8FF', color: '#175CD3' },
  DELETED: { bg: '#F2F4F7', color: '#344054' },
  CANCELLED: { bg: '#ECFDF3', color: '#067647' },
};

export const RETENTION_EXECUTION_LABELS: Record<string, string> = {
  PENDING: 'Chờ thực thi',
  PROCESSING: 'Đang thực thi',
  COMPLETED: 'Đã hoàn tất',
  FAILED: 'Thực thi lỗi',
};

export function retentionStatusLabel(status: string) {
  return RETENTION_STATUS_LABELS[status] || status;
}

export function retentionExecutionLabel(status: string | null) {
  if (!status) return 'Chưa chạy';
  return RETENTION_EXECUTION_LABELS[status] || status;
}

export interface RetentionSummary {
  total: number;
  due: number;
  pending: number;
  scheduled: number;
  cancelled: number;
  deleted: number;
  processing: number;
}

export function summarizeRetentionCases(cases: RetentionCase[]): RetentionSummary {
  const summary: RetentionSummary = { total: cases.length, due: 0, pending: 0, scheduled: 0, cancelled: 0, deleted: 0, processing: 0 };
  for (const item of cases) {
    if (item.is_due && (item.status === 'PENDING' || item.status === 'SCHEDULED_FOR_DELETION')) summary.due += 1;
    if (item.status === 'PENDING') summary.pending += 1;
    else if (item.status === 'SCHEDULED_FOR_DELETION') summary.scheduled += 1;
    else if (item.status === 'CANCELLED') summary.cancelled += 1;
    else if (item.status === 'DELETED') summary.deleted += 1;
    if (item.execution_status === 'PROCESSING' || item.execution_in_progress_or_recovery) summary.processing += 1;
  }
  return summary;
}

/** Xác nhận chỉ có nghĩa khi case còn chờ, đã đến hạn và không có lần thực thi dở. */
export function canConfirmRetentionCase(item: RetentionCase) {
  return item.status === 'PENDING' && item.is_due && !item.execution_in_progress_or_recovery
    && item.execution_status !== 'PROCESSING';
}

/** Huỷ được trước khi thực thi; case đã xoá hoặc đang xoá thì không. */
export function canCancelRetentionCase(item: RetentionCase) {
  if (item.execution_in_progress_or_recovery || item.execution_status === 'PROCESSING') return false;
  return item.status === 'PENDING' || item.status === 'SCHEDULED_FOR_DELETION';
}

/** Hồ sơ đã bị xoá thì không còn timeline quyết định để xem. */
export function hasApplicationTimeline(item: Pick<RetentionCase, 'application_id' | 'status'>) {
  return Boolean(item.application_id) && item.status !== 'DELETED';
}

export function retentionDate(value: string | null, locale: string) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString(locale);
}

/** Số ngày còn lại tới hạn xoá; âm nghĩa là đã quá hạn. */
export function daysUntilRetentionDue(dueDate: string | null, now: Date = new Date()) {
  if (!dueDate) return null;
  const due = new Date(dueDate).getTime();
  if (Number.isNaN(due)) return null;
  return Math.ceil((due - now.getTime()) / 86_400_000);
}
