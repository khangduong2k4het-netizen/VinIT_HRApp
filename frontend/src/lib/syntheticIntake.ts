/** User-facing messages for the synthetic careers flow; never infer duplicate identities. */
export function careersFailure(status: number | null, detail: unknown): string {
  if (status === null) return 'Không biết hồ sơ đã được nhận hay chưa. Giữ nguyên toàn bộ form, file và mã rút; nhấn gửi lại để kiểm tra an toàn.';
  if (status === 409 && detail === 'Mã yêu cầu đã được sử dụng cho nội dung khác') return 'Mã yêu cầu đã dùng với nội dung khác. Không sửa form sau khi gửi; liên hệ HR để kiểm tra trước khi tạo yêu cầu mới.';
  if (status === 410) return 'Yêu cầu đã hết hạn. Liên hệ HR kiểm tra trước khi tạo yêu cầu mới.';
  if (status === 503) return 'Dịch vụ kiểm tra hoặc lưu trữ chưa sẵn sàng. Giữ nguyên form và thử lại sau; không gửi hồ sơ thật.';
  if (status === 422) return 'Thông tin hoặc tệp chưa hợp lệ. Hãy kiểm tra các trường trong form.';
  if (typeof detail === 'string' && detail.length <= 300) return detail;
  return 'Không thể gửi hồ sơ thử nghiệm. Giữ nguyên form và liên hệ HR nếu lỗi tiếp diễn.';
}
