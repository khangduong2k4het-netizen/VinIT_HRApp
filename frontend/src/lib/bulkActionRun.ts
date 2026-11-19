/**
 * Một lô hành động trên trang xếp hạng: mỗi hồ sơ có sẵn danh sách bước hợp lệ
 * của ma trận chuyển trạng thái hiện có, và kết quả được ghi lại theo từng bước.
 *
 * Nhờ vậy khi một hồ sơ lỗi giữa lô, màn hình nói được chính xác hồ sơ đã dừng ở
 * đâu, và lần thử lại chỉ đi tiếp phần còn thiếu — không chạy lại hồ sơ đã xong
 * và không lặp lại bước đã ghi vào lịch sử.
 */
export type BulkActionMode = 'shortlist' | 'reject';
/**
 * `interrupted` là hồ sơ đang được ghi đúng lúc lô bị dừng (đóng tab, mất mạng):
 * không biết bước cuối đã lưu hay chưa, nên không được tự chạy lại — HR mở hồ sơ
 * kiểm tra trạng thái thật.
 */
export type BulkRowState = 'pending' | 'running' | 'done' | 'failed' | 'interrupted';

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

/**
 * Dòng đang chạy khi lô bị dừng trở thành `interrupted`: kết quả của bước cuối
 * không rõ, nên giữ lại số bước đã biết nhưng không tự chạy lại.
 */
export function markInterrupted(rows: BulkRunRow[]): BulkRunRow[] {
  return rows.map(row => (row.state === 'running' ? { ...row, state: 'interrupted' as BulkRowState } : row));
}

export interface BulkRunProgress {
  total: number;
  done: number;
  failed: number;
  pending: number;
  running: number;
  interrupted: number;
  /** Số hồ sơ đã có kết quả cuối (xong, lỗi hoặc không rõ). */
  finished: number;
}

export function bulkRunProgress(rows: BulkRunRow[]): BulkRunProgress {
  const progress: BulkRunProgress = { total: rows.length, done: 0, failed: 0, pending: 0, running: 0, interrupted: 0, finished: 0 };
  for (const row of rows) {
    progress[row.state] += 1;
    if (row.state !== 'pending' && row.state !== 'running') progress.finished += 1;
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

/**
 * Lô được giữ trên máy để đóng tab không mất biên bản: mất mạng hay đóng trình
 * duyệt giữa lô 30–50 hồ sơ từng khiến HR phải tự dò lại từ đầu.
 */
export const BULK_RUN_STORAGE_VERSION = 1;

export interface StoredBulkRun {
  version: number;
  position_id: string;
  mode: BulkActionMode;
  reason: string;
  rows: BulkRunRow[];
  saved_at: number;
}

export function bulkRunStorageKey(positionId: string) {
  return `hra-bulk-run:${positionId}`;
}

export function toStoredBulkRun(
  positionId: string,
  mode: BulkActionMode,
  reason: string,
  rows: BulkRunRow[],
  now: number = Date.now(),
): StoredBulkRun {
  return {
    version: BULK_RUN_STORAGE_VERSION,
    position_id: positionId,
    mode,
    reason,
    rows: markInterrupted(rows),
    saved_at: now,
  };
}

const ROW_STATES: BulkRowState[] = ['pending', 'running', 'done', 'failed', 'interrupted'];

/** Kiểm tra từng dòng trước khi tin dữ liệu đọc từ localStorage. */
function isBulkRunRow(value: unknown): value is BulkRunRow {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<BulkRunRow>;
  return typeof row.application_id === 'string' && row.application_id.length > 0
    && typeof row.from_status === 'string'
    && Array.isArray(row.steps) && row.steps.every(step => typeof step === 'string')
    && typeof row.applied === 'number' && Number.isInteger(row.applied)
    && row.applied >= 0 && row.applied <= row.steps.length
    && (row.reached_status == null || typeof row.reached_status === 'string')
    && (row.error == null || typeof row.error === 'string')
    && typeof row.candidate_name === 'string'
    && ROW_STATES.includes(row.state as BulkRowState);
}

/**
 * Đọc lại lô đã lưu. Dữ liệu lạ, sai phiên bản hoặc của vị trí khác bị bỏ qua
 * hoàn toàn, để một payload hỏng không dựng ra biên bản giả.
 */
export function parseStoredBulkRun(raw: string | null, positionId: string): StoredBulkRun | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredBulkRun>;
    if (!parsed || parsed.version !== BULK_RUN_STORAGE_VERSION) return null;
    if (parsed.position_id !== positionId) return null;
    if (parsed.mode !== 'shortlist' && parsed.mode !== 'reject') return null;
    if (!Array.isArray(parsed.rows) || parsed.rows.length === 0) return null;
    if (!parsed.rows.every(isBulkRunRow)) return null;
    return {
      version: parsed.version,
      position_id: parsed.position_id,
      mode: parsed.mode,
      reason: typeof parsed.reason === 'string' ? parsed.reason : '',
      rows: markInterrupted(parsed.rows),
      saved_at: typeof parsed.saved_at === 'number' ? parsed.saved_at : 0,
    };
  } catch {
    return null;
  }
}

/** Còn hồ sơ chưa có kết quả cuối nghĩa là lô đang dở và cần được nhắc lại. */
export function hasUnfinishedRows(rows: BulkRunRow[]) {
  return rows.some(row => row.state !== 'done');
}
