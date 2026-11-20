/**
 * Link của một dòng "Việc cần làm".
 *
 * Hàng đợi trước đây chỉ mở danh sách đã lọc, nên mỗi việc tốn thêm hai lần
 * điều hướng trước khi HR làm được gì. Khi backend biết hồ sơ nào đang chờ lâu
 * nhất trong nhóm đó, dòng việc mở thẳng hồ sơ ấy và giữ nguyên bộ lọc trong
 * URL — trang hồ sơ dựng lại hàng đợi từ chính URL đó nên tiến độ "3/17" vẫn
 * đúng. Không có id thì rơi về danh sách như cũ, không link nào bị hỏng.
 */
import type { WorkQueueItem } from '@/types';

type WorkQueueLink = Pick<WorkQueueItem, 'target' | 'next_application_id'>;

function searchSuffix(search?: string): string {
  return search ? `?${search}` : '';
}

/** Danh sách đã lọc — đích cũ, vẫn dùng cho dòng việc không gắn với hồ sơ nào. */
export function workQueueListHref(item: Pick<WorkQueueItem, 'target'>): string {
  return `${item.target.pathname}${searchSuffix(item.target.search)}`;
}

/**
 * Hồ sơ kế tiếp của đúng nhóm việc này, hoặc `null` khi việc không gắn với một
 * hồ sơ cụ thể (thiết lập vị trí, hạn ứng tuyển, shortlist chờ phản hồi…).
 */
export function workQueueNextHref(item: WorkQueueLink): string | null {
  const applicationId = (item.next_application_id || '').trim();
  if (!applicationId) return null;
  const listPath = item.target.pathname.replace(/\/+$/, '');
  return `${listPath}/${encodeURIComponent(applicationId)}${searchSuffix(item.target.search)}`;
}
