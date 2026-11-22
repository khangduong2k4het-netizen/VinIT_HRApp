/**
 * "Còn 2 giờ" / "Bắt đầu sau 15 phút" — dễ đọc hơn giờ tuyệt đối khi đang trong
 * ngày. Giờ tuyệt đối vẫn phải hiện kèm: người dùng cần biết chính xác mấy giờ.
 *
 * Trả `null` khi buổi đã qua hoặc còn quá xa (hơn 7 ngày): "còn 43 ngày" không
 * giúp ai quyết định gì, và ở khoảng đó người ta đọc ngày tháng tự nhiên hơn.
 */
export function countdownLabel(startsAt: string, now: Date = new Date()): string | null {
  const start = new Date(startsAt);
  if (Number.isNaN(start.getTime())) return null;
  const minutes = Math.round((start.getTime() - now.getTime()) / 60000);
  if (minutes < 0) return null;
  if (minutes < 5) return 'Sắp bắt đầu';
  if (minutes < 60) return `Còn ${minutes} phút`;
  if (minutes < 24 * 60) {
    const hours = Math.round(minutes / 60);
    return `Còn ${hours} giờ`;
  }
  const days = Math.floor(minutes / (24 * 60));
  if (days <= 7) return `Còn ${days} ngày`;
  return null;
}
