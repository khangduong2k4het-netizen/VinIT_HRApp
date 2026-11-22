/**
 * Tuần của "Lịch của tôi" — logic thuần, tách khỏi trang để test được.
 *
 * Cùng lý do với `careersFilter.ts`: phần tự viết là phần dễ sai, còn phần còn
 * lại của trang chỉ là chuyển dữ liệu sang MUI.
 *
 * Ba chỗ dễ sai:
 *
 * 1. **Tuần bắt đầu thứ Hai**, không phải Chủ nhật. `getUTCDay()` trả 0 cho Chủ
 *    nhật, nên công thức `weekday - 1` đẩy Chủ nhật sang tuần SAU. Lịch làm việc
 *    Việt Nam bắt đầu thứ Hai; để Chủ nhật ở tuần sau thì hai ngày cuối tuần
 *    nằm ở hai đầu khác nhau và tuần đọc rất khó.
 * 2. **Cộng ngày qua tháng/năm** phải dùng `setUTCDate`, không cộng mili-giây —
 *    cộng 86 400 000 ms sẽ lệch ở múi giờ có DST (Việt Nam không có, nhưng
 *    người dùng có thể ở múi khác).
 * 3. **Gom nhóm theo ngày Việt Nam**, không theo ngày UTC: buổi 23:00 UTC là
 *    06:00 hôm sau ở Việt Nam.
 */

export const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh';

/** Thứ Hai của tuần chứa `date`, giữ nguyên phần giờ. */
export function mondayOf(date: Date): Date {
  const copy = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const weekday = copy.getUTCDay();            // 0 = Chủ nhật
  const offset = weekday === 0 ? 6 : weekday - 1;
  copy.setUTCDate(copy.getUTCDate() - offset);
  return copy;
}

/** Cộng/trừ ngày, không sửa đối tượng gốc. */
export function addDays(date: Date, days: number): Date {
  const copy = new Date(date.getTime());
  copy.setUTCDate(copy.getUTCDate() + days);
  return copy;
}

/** Khoá ngày theo giờ Việt Nam, dạng `YYYY-MM-DD`. */
export function vietnamDayKey(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso;
  return new Intl.DateTimeFormat('en-CA', { timeZone: VIETNAM_TIME_ZONE }).format(date);
}
