/**
 * Lọc danh sách việc làm theo từ khoá, ngay trên dữ liệu đã tải.
 *
 * Tách ra khỏi trang để test được mà không cần render React: đây là logic tự
 * viết, còn phần còn lại của trang là chuyển dữ liệu từ API sang MUI.
 *
 * Vì sao lọc tại chỗ thay vì gọi API: số tin còn hạn đủ nhỏ, và gõ tới đâu thấy
 * tới đó thì không có độ trễ mạng chen vào giữa phím bấm và kết quả.
 */
export type SearchableJob = {
  title: string;
  org_unit?: string | null;
  work_location?: string | null;
};

export function filterJobs<T extends SearchableJob>(jobs: T[], query: string): T[] {
  // Không cắt dấu: tiếng Việt gõ không dấu rất phổ biến, nhưng tự chuẩn hoá
  // dấu là đoán ý người dùng — "thực" và "thuc" có thể là hai từ khác nhau.
  // Chỉ cần khớp đúng những gì người ta gõ.
  const needle = query.trim().toLowerCase();
  if (!needle) return jobs;
  return jobs.filter(job =>
    job.title.toLowerCase().includes(needle)
    || (job.org_unit || '').toLowerCase().includes(needle)
    || (job.work_location || '').toLowerCase().includes(needle));
}
