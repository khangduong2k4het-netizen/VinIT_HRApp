/**
 * Câu hiển thị của một thông báo lịch phỏng vấn.
 *
 * Tách khỏi component để test được mà không render React — cùng lý do với
 * `workQueueLabels.ts` và `careerViewer.ts`.
 *
 * Nguyên tắc: câu thông báo phải nói được **cái gì đổi**, không chỉ "có thay
 * đổi". Người đọc lúc 8h sáng cần biết "buổi 14:00 đổi sang 15:30", không cần
 * biết "lịch vừa được cập nhật". Vì vậy `payload` mang giờ cũ/mới, và hàm này
 * đọc nó — backend cố ý không chép nội dung buổi vào thông báo.
 */
import type { InterviewNotification } from '@/types';

/** Giờ Việt Nam, gọn: "14:00 01/12". */
export function shortVietnamTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit',
    day: '2-digit', month: '2-digit', hour12: false,
  }).format(date);
}

const HEADLINE: Record<InterviewNotification['kind'], string> = {
  INTERVIEW_CREATED: 'Bạn được mời phỏng vấn',
  INTERVIEW_UPDATED: 'Lịch phỏng vấn đã thay đổi',
  INTERVIEW_CANCELLED: 'Buổi phỏng vấn đã bị huỷ',
  PARTICIPANTS_CHANGED: 'Người tham gia buổi đã thay đổi',
  SCORECARD_DUE_SOON: 'Phiếu chấm sắp tới hạn',
};

export function notificationText(item: Pick<InterviewNotification, 'kind' | 'payload' | 'round_number' | 'starts_at'>): string {
  const headline = HEADLINE[item.kind] ?? 'Lịch phỏng vấn';
  const round = item.round_number ? `vòng ${item.round_number}` : '';
  const when = shortVietnamTime(item.starts_at);
  const detail = [round, when].filter(Boolean).join(' · ');
  const payload = item.payload || {};

  if (item.kind === 'INTERVIEW_UPDATED' && payload.starts_at_from && payload.starts_at_to) {
    const from = shortVietnamTime(String(payload.starts_at_from));
    const to = shortVietnamTime(String(payload.starts_at_to));
    // Chỉ nói giờ khi giờ THẬT SỰ đổi. Sửa mỗi phòng họp mà hiện "14:00 → 14:00"
    // thì câu thông báo vừa dài vừa vô nghĩa.
    if (from && to && from !== to) return `${headline}: ${from} → ${to}`;
  }
  return detail ? `${headline} (${detail})` : headline;
}

/** Gom nhãn để badge không đếm trùng một sự kiện hai lần. */
export function unreadCount(items: Array<Pick<InterviewNotification, 'read_at'>>): number {
  return items.filter(item => !item.read_at).length;
}
