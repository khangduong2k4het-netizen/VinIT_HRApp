/**
 * Một lô hành động trên trang xếp hạng: mỗi hồ sơ có sẵn danh sách bước hợp lệ
 * của ma trận chuyển trạng thái hiện có, và kết quả được ghi lại theo từng bước.
 *
 * Nhờ vậy khi một hồ sơ lỗi giữa lô, màn hình nói được chính xác hồ sơ đã dừng ở
 * đâu, và lần thử lại chỉ đi tiếp phần còn thiếu — không chạy lại hồ sơ đã xong
 * và không lặp lại bước đã ghi vào lịch sử.
 */
export type BulkActionMode = 'shortlist' | 'reject';
export type BulkRowState = 'pending' | 'running' | 'done' | 'failed';

export interface BulkRowInput {
  application_id: string;
  candidate_name?: string | null;
  application_status: string;
}

export interface BulkRunRow {
  application_id: string;
  candidate_name: string;
  from_status: string;
  /** Các trạng thái phải đi qua, theo đúng thứ tự của ma trận chuyển trạng thái. */
  steps: string[];
  /** Số bước đã ghi thành công; cũng là vị trí bắt đầu của lần thử lại. */
  applied: number;
  /** Trạng thái hiện tại trên máy chủ theo những gì lô này đã ghi. */
  reached_status: string | null;
  state: BulkRowState;
  error: string | null;
}

/**
 * Các bước của một hồ sơ trong lô. Shortlist hồ sơ Mới phải qua hai bước hợp lệ
 * (Mới → Đang xem → Shortlist); hồ sơ đã Shortlist hoặc ngoài sàng lọc không có
 * bước nào, nên nó không bao giờ bị đưa vào lô rồi báo lỗi.
 */
export function bulkSteps(mode: BulkActionMode, status: string): string[] {
  if (mode === 'reject') return status === 'REJECTED_SCREENING' ? [] : ['REJECTED_SCREENING'];
  if (status === 'NEW') return ['IN_REVIEW', 'SHORTLIST'];
  if (status === 'IN_REVIEW') return ['SHORTLIST'];
  return [];
}

export function createBulkRun(items: BulkRowInput[], mode: BulkActionMode): BulkRunRow[] {
  return items
    .map(item => ({
      application_id: item.application_id,
      candidate_name: (item.candidate_name || '').trim(),
      from_status: item.application_status,
      steps: bulkSteps(mode, item.application_status),
      applied: 0,
      reached_status: null,
      state: 'pending' as BulkRowState,
      error: null,
    }))
    .filter(row => row.steps.length > 0);
}

/** Phần còn lại của một hồ sơ, tính từ số bước đã ghi — dùng cho lần thử lại. */
export function remainingSteps(row: BulkRunRow): string[] {
  return row.steps.slice(row.applied);
}

/** Đưa các dòng lỗi về trạng thái chờ, giữ nguyên số bước đã ghi để đi tiếp. */
export function retryFailed(rows: BulkRunRow[]): BulkRunRow[] {
  return rows.map(row => (row.state === 'failed' ? { ...row, state: 'pending' as BulkRowState, error: null } : row));
}

export interface BulkRunProgress {
  total: number;
  done: number;
  failed: number;
  pending: number;
  running: number;
  /** Số hồ sơ đã có kết quả cuối (xong hoặc lỗi). */
  finished: number;
}

export function bulkRunProgress(rows: BulkRunRow[]): BulkRunProgress {
  const progress: BulkRunProgress = { total: rows.length, done: 0, failed: 0, pending: 0, running: 0, finished: 0 };
  for (const row of rows) {
    progress[row.state] += 1;
    if (row.state === 'done' || row.state === 'failed') progress.finished += 1;
  }
  return progress;
}

/**
 * Chỗ dừng của một hồ sơ lỗi: bước đã ghi gần nhất và đích còn thiếu. Hồ sơ lỗi
 * ngay bước đầu không có chỗ dừng — nói "đã sang Đang xem" khi chưa ghi gì là sai.
 */
export function stopPoint(row: BulkRunRow): { reached: string; target: string } | null {
  if (row.state !== 'failed' || row.applied === 0 || !row.reached_status) return null;
  return { reached: row.reached_status, target: row.steps[row.steps.length - 1] };
}
