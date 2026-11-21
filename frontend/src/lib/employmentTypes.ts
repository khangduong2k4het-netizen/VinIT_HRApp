/**
 * Loại việc làm, dùng chung cho form vị trí và bộ lọc trang tuyển dụng.
 *
 * Vì sao là danh sách đóng thay vì ô nhập tự do: giá trị này vừa là dữ liệu
 * vừa là nhãn hiển thị trên /careers. Gõ tự do thì "Full-time", "Full time",
 * "fulltime" thành ba loại khác nhau và thanh danh mục trên trang tuyển dụng
 * có ba mục gần giống hệt — mỗi mục chỉ chứa một phần tin.
 *
 * Đây là ràng buộc ở giao diện, không phải ở DB: dữ liệu cũ có thể mang giá trị
 * khác và vẫn hiển thị bình thường (bộ lọc dựng từ dữ liệu thật).
 */
export const EMPLOYMENT_TYPES = [
  'Toàn thời gian',
  'Bán thời gian',
  'Thực tập',
  'Hợp đồng',
  'Thời vụ',
] as const;

export type EmploymentType = typeof EMPLOYMENT_TYPES[number];
