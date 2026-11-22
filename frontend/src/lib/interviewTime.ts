/**
 * Chuyển đổi và kiểm tra giờ cho biểu mẫu phỏng vấn.
 *
 * Tách khỏi component vì đây là phần **dễ sai** và phần còn lại chỉ là MUI: cùng
 * lý do với `interviewWeek.ts`.
 */

/** Múi giờ Việt Nam cố định UTC+7, không có DST. */
export const VIETNAM_OFFSET = '+07:00';

/**
 * `<input type="datetime-local">` (giờ Việt Nam) → chuỗi ISO có offset.
 *
 * Trả `null` khi chuỗi không phải giờ hợp lệ. Trước đây hàm chỉ nối `+07:00`:
 * người dùng gõ vào ô trống hoặc trình duyệt trả chuỗi lạ thì giá trị
 * `"abc+07:00"` được gửi lên, và máy chủ trả 422 với thông báo khó hiểu
 * ("value is not a valid datetime") chứ không nói ô nào sai.
 */
export function vietnamLocalToUtc(local: string): string | null {
  // Hình dạng duy nhất `<input type="datetime-local">` phát ra: `YYYY-MM-DDTHH:mm`
  // (một số trình duyệt thêm `:ss`). Kiểm bằng mẫu thay vì `new Date()`: `new Date`
  // nhận cả "2026-13-45" rồi tự sửa thành tháng sau — sai mà không báo.
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(local);
  if (!match) return null;
  const [, year, month, day, hour, minute, second = '00'] = match;
  const values = [Number(year), Number(month), Number(day), Number(hour), Number(minute), Number(second)];
  const [y, mo, d, h, mi, s] = values;
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || s > 59) return null;
  // Kiểm ngày có thật: 2026-02-30 phải bị loại, và `new Date` một mình thì tự
  // chuyển thành 2026-03-02.
  const probe = new Date(Date.UTC(y, mo - 1, d, h, mi, s));
  if (probe.getUTCFullYear() !== y || probe.getUTCMonth() !== mo - 1 || probe.getUTCDate() !== d) return null;
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${VIETNAM_OFFSET}`;
}

/**
 * Kiểm toàn bộ biểu mẫu đặt lịch **trước** khi gửi. Trả khóa lỗi, hoặc `null`.
 *
 * Đặt ở đây để dialog chỉ còn việc hiển thị: mọi luật về thời gian nằm một chỗ,
 * và test được mà không render React.
 */
export function validateInterviewForm(form: {
  startsAt: string; endsAt: string; locationKind: string; locationText: string;
  reviewerCount: number;
}): string | null {
  if (!form.startsAt || !form.endsAt) return 'Cần nhập giờ bắt đầu và kết thúc.';
  const starts = vietnamLocalToUtc(form.startsAt);
  const ends = vietnamLocalToUtc(form.endsAt);
  if (!starts || !ends) return 'Giờ không hợp lệ. Nhập theo dạng ngày/tháng/năm và giờ:phút.';
  if (new Date(ends) <= new Date(starts)) return 'Kết thúc phải sau bắt đầu.';
  if (!form.reviewerCount) return 'Cần chọn ít nhất một người phỏng vấn.';
  if (form.locationKind !== 'ONSITE' && !form.locationText.trim()) {
    return 'Hẹn online hoặc qua điện thoại cần link hoặc số liên hệ.';
  }
  return null;
}
