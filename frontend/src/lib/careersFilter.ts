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
    matches(job.title, needle)
    || matches(job.org_unit || '', needle)
    || matches(job.work_location || '', needle));
}

/**
 * Khớp theo **từ**, không phải chuỗi con giữa chữ.
 *
 * Vì sao: tìm "IT" bằng `includes` sẽ khớp cả "with", "Digital", "recruit" —
 * một từ khoá hai chữ cái lọc ra gần như mọi tin, trông như bộ lọc hỏng. Ở đây
 * "IT" chỉ khớp khi nó là một từ (hoặc đầu từ, để gõ "back" vẫn ra "backend").
 */
function matches(text: string, needle: string): boolean {
  const haystack = text.toLowerCase();
  if (haystack.includes(needle)) {
    // Chuỗi con khớp: chỉ nhận nếu nằm ở ranh giới từ. Ranh giới là đầu/cuối
    // chuỗi hoặc ký tự không phải chữ-số. Dùng regex thay vì tách theo khoảng
    // trắng để "backend," hay "(backend)" vẫn khớp.
    const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}`, 'u').test(haystack);
  }
  return false;
}
