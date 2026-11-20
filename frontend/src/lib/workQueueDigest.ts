/**
 * "Có gì mới từ lần mở dashboard trước?"
 *
 * Hàng đợi việc chỉ hiện khi HR tự mở dashboard, nên một CV xử lý xong lúc 9h chỉ
 * được biết khi ai đó nhớ ra phải kiểm tra. Ở đây không thêm backend: chụp lại
 * số việc theo từng dòng (`item_id`) mỗi lần xem, rồi so lần sau với lần trước.
 * Số việc tăng nghĩa là có hồ sơ mới rơi vào nhóm đó.
 *
 * Chỉ đọc localStorage của chính trình duyệt này: cùng giới hạn với số đo UX, và
 * không ghi tên ứng viên hay nội dung hồ sơ.
 */
import type { WorkQueueItem } from '@/types';

export const WORK_QUEUE_SNAPSHOT_KEY = 'hra-work-queue-snapshot';
/**
 * Mốc cũ hơn ngưỡng này không còn là "lần trước" đáng so: sau một tuần nghỉ,
 * mọi thứ đều "mới" và con số mất nghĩa.
 */
export const WORK_QUEUE_BASELINE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

export interface WorkQueueSnapshot {
  takenAt: number;
  /** `item_id` -> số việc của dòng đó tại thời điểm chụp. */
  counts: Record<string, number>;
}

export interface WorkQueueIncrease {
  itemId: string;
  type: WorkQueueItem['type'];
  positionTitle: string | null;
  /** Số việc tăng thêm so với lần trước (luôn > 0). */
  added: number;
}

function browserStorage(): StorageLike | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

export function snapshotWorkQueue(
  items: Array<Pick<WorkQueueItem, 'item_id' | 'count'>>,
  now: number = Date.now(),
): WorkQueueSnapshot {
  const counts: Record<string, number> = {};
  for (const item of items) {
    if (!item.item_id) continue;
    counts[item.item_id] = Math.max(0, Math.trunc(Number(item.count) || 0));
  }
  return { takenAt: now, counts };
}

export function increasesSince(
  snapshot: WorkQueueSnapshot | null,
  items: Array<Pick<WorkQueueItem, 'item_id' | 'type' | 'position_title' | 'count'>>,
  now: number = Date.now(),
): WorkQueueIncrease[] {
  if (!snapshot) return [];
  if (!Number.isFinite(snapshot.takenAt)) return [];
  if (now - snapshot.takenAt > WORK_QUEUE_BASELINE_MAX_AGE_MS) return [];
  const increases: WorkQueueIncrease[] = [];
  for (const item of items) {
    const previous = snapshot.counts[item.item_id] ?? 0;
    const added = (Number(item.count) || 0) - previous;
    if (added <= 0) continue;
    increases.push({
      itemId: item.item_id,
      type: item.type,
      positionTitle: item.position_title ?? null,
      added,
    });
  }
  return increases;
}

/** Tổng số việc mới — con số trên dải tóm tắt, không phải số dòng. */
export function totalNewWork(increases: WorkQueueIncrease[]): number {
  return increases.reduce((total, item) => total + item.added, 0);
}

export function readWorkQueueSnapshot(storage: StorageLike | null = browserStorage()): WorkQueueSnapshot | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(WORK_QUEUE_SNAPSHOT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (!Number.isFinite(parsed.takenAt) || !parsed.counts || typeof parsed.counts !== 'object') return null;
    const counts: Record<string, number> = {};
    for (const [key, value] of Object.entries(parsed.counts as Record<string, unknown>)) {
      if (typeof key !== 'string' || !key) continue;
      if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) continue;
      counts[key] = Math.trunc(value);
    }
    return { takenAt: parsed.takenAt, counts };
  } catch {
    return null;
  }
}

export function writeWorkQueueSnapshot(
  snapshot: WorkQueueSnapshot,
  storage: StorageLike | null = browserStorage(),
): void {
  if (!storage) return;
  try {
    storage.setItem(WORK_QUEUE_SNAPSHOT_KEY, JSON.stringify(snapshot));
  } catch {
    // Không lưu được thì lần sau chỉ thiếu dải "có gì mới", không ảnh hưởng việc.
  }
}
