/**
 * Phím tắt cho vòng xác minh hồ sơ.
 *
 * Tách khỏi trang để kiểm được bằng test thuần: việc xác nhận/từ chối từng tiêu
 * chí lặp lại hàng chục lần mỗi ngày, nên một phím lỡ tay sẽ ghi một quyết định
 * sai vào lịch sử. Vì thế mọi điều kiện chặn (đang gõ chữ, có phím điều khiển,
 * không có gì để xác nhận) nằm ở đây thay vì rải trong component.
 */
export type ReviewShortcut =
  | 'next-criterion'
  | 'prev-criterion'
  | 'confirm'
  | 'reject'
  | 'open-page'
  | 'next-application'
  | 'finish'
  | 'show-shortcuts';

export interface ReviewShortcutAvailability {
  /** Tiêu chí đang chọn có thể xác nhận trích dẫn ngay (còn chờ HR, có quyền). */
  canConfirm: boolean;
  /** Tiêu chí đang chọn có thể đánh dấu sai (mở hộp thoại nhập lý do). */
  canReject: boolean;
  /** Đang chọn một tiêu chí có trang CV để mở. */
  canOpenPage: boolean;
  /** Hồ sơ này nằm trong hàng đợi và còn hồ sơ kế tiếp. */
  hasNextApplication: boolean;
  /** Người xem có quyền hoàn tất hồ sơ (cùng điều kiện với nút "Đã xử lý xong"). */
  canFinish: boolean;
}

export interface ReviewKeyEvent {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  defaultPrevented?: boolean;
}

function tagNameOf(target: unknown): string {
  if (!target || typeof target !== 'object') return '';
  return String((target as { tagName?: unknown }).tagName || '').toUpperCase();
}

/**
 * Đang gõ trong ô nhập thì phím là chữ, không phải lệnh. Hộp thoại từ chối
 * trích dẫn mở với ô lý do autoFocus, nên đây là điều kiện bắt buộc.
 */
export function isTypingTarget(target: unknown): boolean {
  const tag = tagNameOf(target);
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return Boolean(target && typeof target === 'object' && (target as { isContentEditable?: boolean }).isContentEditable);
}

/**
 * Phím này có nghĩa gì trong vòng xác minh? `null` nghĩa là để trình duyệt xử lý
 * như bình thường — không phím nào bị nuốt khi nó không làm gì.
 */
export function reviewShortcut(
  event: ReviewKeyEvent,
  availability: ReviewShortcutAvailability,
  typing: boolean,
): ReviewShortcut | null {
  if (typing || event.defaultPrevented) return null;
  // Ctrl/Cmd/Alt + phím là phím tắt của trình duyệt hoặc của người dùng.
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  switch (key) {
    case 'j':
      return 'next-criterion';
    case 'k':
      return 'prev-criterion';
    case '1':
      return availability.canConfirm ? 'confirm' : null;
    case '2':
      return availability.canReject ? 'reject' : null;
    case 'Enter':
      return availability.canOpenPage ? 'open-page' : null;
    case 'n':
      return availability.hasNextApplication ? 'next-application' : null;
    case 'f':
      // Cùng một cửa với nút "Đã xử lý xong": không có quyền thì phím không làm gì
      // chứ không mở ra một đường hoàn tất thứ hai.
      return availability.canFinish ? 'finish' : null;
    case '?':
      // Phím trợ giúp: luôn mở được, kể cả khi không còn gì để xác nhận.
      return 'show-shortcuts';
    default:
      return null;
  }
}

export interface VerifyableCriterion {
  criterion_id: string;
  result_id?: string | null;
  requires_verification: boolean;
  hr_reviews?: unknown[] | null;
}

/**
 * Tiêu chí HR nên làm tiếp sau khi vừa xác nhận một tiêu chí.
 *
 * Con trỏ cũ đứng lại ở tiêu chí vừa xong, nên lần bấm `1` kế tiếp không làm gì
 * và HR phải tự tìm tiêu chí còn chờ (đo được: 16 phím cho 2 tiêu chí, 7 lần bấm
 * vô ích). Đi tiếp về phía trước; chỉ khi phía trước hết việc mới quay lại tiêu
 * chí còn chờ phía trên, vì bỏ sót nó sẽ im lặng.
 *
 * Trả `null` khi không còn gì chờ — con trỏ giữ nguyên ở tiêu chí vừa xác nhận.
 */
export function nextPendingCriterionId(
  results: VerifyableCriterion[],
  justReviewedCriterionId: string,
): string | null {
  const pending = results.filter(result => result.criterion_id !== justReviewedCriterionId
    && result.requires_verification
    && result.result_id
    && !(result.hr_reviews && result.hr_reviews.length));
  if (!pending.length) return null;
  const reviewedIndex = results.findIndex(result => result.criterion_id === justReviewedCriterionId);
  const after = pending.find(result => results.indexOf(result) > reviewedIndex);
  return (after || pending[0]).criterion_id;
}

/**
 * Dịch chỉ số tiêu chí đang chọn. Dừng ở hai đầu thay vì quay vòng: nhảy từ
 * tiêu chí cuối về đầu mà không báo gì sẽ làm HR xác nhận nhầm tiêu chí.
 */
export function moveCriterionIndex(index: number, length: number, delta: number): number {
  if (length <= 0) return -1;
  const from = index < 0 ? 0 : index;
  return Math.min(length - 1, Math.max(0, from + delta));
}
