/**
 * Đo tác động của chính các cải tiến UX.
 *
 * Bốn lượt trước đều là "cảm giác tốt hơn"; không đo thì không biết cái nào thật
 * sự giúp. Module này ghi bốn loại event nhẹ — mở hồ sơ, rời hồ sơ, hoàn tất hồ
 * sơ, chạy lô hành động — vào localStorage của chính HR.
 *
 * Cố ý không gửi lên máy chủ và không ghi nội dung hồ sơ: chỉ id hồ sơ, thời điểm
 * và thời lượng. Số đo vì thế chỉ nói về trình duyệt này, không phải toàn hệ thống;
 * màn hình phải nói rõ điều đó thay vì trình bày như số liệu toàn cục.
 */
export type UxEventType = 'PROFILE_OPENED' | 'PROFILE_CLOSED' | 'VERIFICATION_COMPLETED' | 'BULK_RUN';

export interface UxEvent {
  type: UxEventType;
  /** epoch ms */
  at: number;
  application_id?: string;
  /** PROFILE_CLOSED: thời gian ở trong hồ sơ; BULK_RUN: thời gian cả lô. */
  duration_ms?: number;
  /** BULK_RUN: số hồ sơ trong lô. */
  records?: number;
  /** BULK_RUN: số hồ sơ lỗi. */
  failed?: number;
}

export const UX_METRICS_STORAGE_KEY = 'hra-ux-events';
export const UX_METRICS_MAX_EVENTS = 500;
/**
 * Một lượt "ở trong hồ sơ" dài hơn ngưỡng này gần như chắc chắn là tab bị bỏ
 * quên (mở qua đêm, khoá máy) chứ không phải thời gian đọc thật; 30 phút là mốc
 * hết phiên quen thuộc của web analytics. Lượt như vậy bị loại khỏi trung vị
 * thay vì bị cắt xuống đúng ngưỡng: cắt sẽ tạo ra một điểm dữ liệu không ai
 * thực sự trải qua và vẫn kéo trung vị lên cao. Event gốc vẫn được giữ nguyên
 * để có thể đếm lại số lượt bị loại.
 */
export const UX_METRICS_MAX_DWELL_MS = 30 * 60_000;

const EVENT_TYPES: UxEventType[] = ['PROFILE_OPENED', 'PROFILE_CLOSED', 'VERIFICATION_COMPLETED', 'BULK_RUN'];

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function browserStorage(): StorageLike | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function sanitizeEvent(value: unknown): UxEvent | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<UxEvent>;
  if (!EVENT_TYPES.includes(candidate.type as UxEventType)) return null;
  if (!isCount(candidate.at) || candidate.at <= 0) return null;
  const event: UxEvent = { type: candidate.type as UxEventType, at: candidate.at };
  if (typeof candidate.application_id === 'string' && candidate.application_id) {
    event.application_id = candidate.application_id.slice(0, 64);
  }
  if (isCount(candidate.duration_ms)) event.duration_ms = candidate.duration_ms;
  if (isCount(candidate.records)) event.records = candidate.records;
  if (isCount(candidate.failed)) event.failed = candidate.failed;
  return event;
}

/** Dữ liệu hỏng hoặc của phiên bản khác bị bỏ qua, không dựng ra số đo giả. */
export function readUxEvents(storage: StorageLike | null = browserStorage()): UxEvent[] {
  if (!storage) return [];
  try {
    const raw = storage.getItem(UX_METRICS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(sanitizeEvent).filter((event): event is UxEvent => event !== null).slice(-UX_METRICS_MAX_EVENTS);
  } catch {
    return [];
  }
}

/**
 * Ghi một event. Chỉ giữ `UX_METRICS_MAX_EVENTS` event gần nhất để localStorage
 * không phình ra theo tháng sử dụng, và mọi lỗi storage đều bị nuốt: đo lường
 * không bao giờ được làm hỏng luồng nghiệp vụ.
 */
export function recordUxEvent(event: UxEvent, storage: StorageLike | null = browserStorage()): UxEvent[] {
  const sanitized = sanitizeEvent(event);
  if (!storage || !sanitized) return readUxEvents(storage);
  try {
    const next = [...readUxEvents(storage), sanitized].slice(-UX_METRICS_MAX_EVENTS);
    storage.setItem(UX_METRICS_STORAGE_KEY, JSON.stringify(next));
    return next;
  } catch {
    return readUxEvents(storage);
  }
}

export function clearUxEvents(storage: StorageLike | null = browserStorage()): void {
  if (!storage) return;
  try {
    storage.removeItem(UX_METRICS_STORAGE_KEY);
  } catch {
    // Không xoá được cũng không ảnh hưởng luồng làm việc.
  }
}

export interface UxImpactSummary {
  profileOpens: number;
  profileCloses: number;
  /** Trung vị thời gian ở trong một hồ sơ, tính bằng phút; bỏ qua các lượt quá dài. */
  medianDwellMinutes: number | null;
  /** Số lượt rời hồ sơ bị loại khỏi trung vị vì dài hơn `UX_METRICS_MAX_DWELL_MS`. */
  ignoredDwellCount: number;
  verifiedProfiles: number;
  /** Trung bình từ lần mở hồ sơ đầu tiên tới lúc hoàn tất, tính bằng phút. */
  averageCompletionMinutes: number | null;
  bulkRuns: number;
  bulkRecords: number;
  bulkFailedRecords: number;
  /** Tỉ lệ hồ sơ lỗi trong các lô đã chạy; null khi chưa chạy lô nào. */
  bulkFailureRate: number | null;
  bulkAverageMinutes: number | null;
  /** Event cũ nhất còn giữ, để màn hình nói được khoảng thời gian đo. */
  sampleSince: number | null;
}

function median(values: number[]) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

const toMinutes = (milliseconds: number) => Math.round((milliseconds / 60_000) * 10) / 10;

export function summarizeUxImpact(events: UxEvent[]): UxImpactSummary {
  const opens = events.filter(event => event.type === 'PROFILE_OPENED');
  const closes = events.filter(event => event.type === 'PROFILE_CLOSED' && isCount(event.duration_ms));
  const completions = events.filter(event => event.type === 'VERIFICATION_COMPLETED' && event.application_id);
  const bulkRuns = events.filter(event => event.type === 'BULK_RUN');

  const dwell = closes.map(event => event.duration_ms as number);
  // Tab để quên qua đêm không phải thời gian xem hồ sơ. Một lượt như vậy đủ để
  // kéo trung vị sai hẳn, nên nó không được tham gia tính trung vị.
  const plausibleDwell = dwell.filter(value => value <= UX_METRICS_MAX_DWELL_MS);
  const ignoredDwellCount = dwell.length - plausibleDwell.length;
  const medianDwellMinutes = median(plausibleDwell);

  // Hoàn tất được ghép với lần mở hồ sơ SỚM NHẤT trước nó; mở lại hồ sơ nhiều lần
  // không được làm thời gian xử lý ngắn đi một cách giả tạo.
  const completionDurations: number[] = [];
  for (const completion of completions) {
    const firstOpen = opens
      .filter(event => event.application_id === completion.application_id && event.at <= completion.at)
      .sort((a, b) => a.at - b.at)[0];
    if (firstOpen) completionDurations.push(completion.at - firstOpen.at);
  }

  const bulkRecords = bulkRuns.reduce((total, event) => total + (event.records || 0), 0);
  const bulkFailedRecords = bulkRuns.reduce((total, event) => total + (event.failed || 0), 0);
  const timedBulkRuns = bulkRuns.filter(event => isCount(event.duration_ms)).map(event => event.duration_ms as number);

  return {
    profileOpens: opens.length,
    profileCloses: closes.length,
    medianDwellMinutes: medianDwellMinutes == null ? null : toMinutes(medianDwellMinutes),
    ignoredDwellCount,
    verifiedProfiles: new Set(completions.map(event => event.application_id)).size,
    averageCompletionMinutes: completionDurations.length
      ? toMinutes(completionDurations.reduce((total, value) => total + value, 0) / completionDurations.length)
      : null,
    bulkRuns: bulkRuns.length,
    bulkRecords,
    bulkFailedRecords,
    bulkFailureRate: bulkRecords > 0 ? Math.round((bulkFailedRecords / bulkRecords) * 1000) / 1000 : null,
    bulkAverageMinutes: timedBulkRuns.length
      ? toMinutes(timedBulkRuns.reduce((total, value) => total + value, 0) / timedBulkRuns.length)
      : null,
    sampleSince: events.length ? Math.min(...events.map(event => event.at)) : null,
  };
}
