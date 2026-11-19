export const REVIEW_LABELS: Record<string, string> = {
  PENDING: 'Chờ kiểm định', IN_REVIEW: 'Đang kiểm định', COMPLETED: 'Đã kiểm định',
  CONFIRMED: 'Đã xác nhận', DISMISSED: 'Đã bỏ qua',
  RANDOM_SAMPLE: 'Mẫu ngẫu nhiên', SINGLE_MANDATORY_MISS: 'Một tiêu chí bắt buộc chưa đáp ứng',
  BORDERLINE_COVERAGE: 'Độ phủ sát ngưỡng', INCORRECT_EVIDENCE: 'Bằng chứng không chính xác',
  MISSING_CONTENT: 'Bỏ sót nội dung', INCORRECT_FACT: 'Thông tin trích xuất sai',
  OCR_ERROR: 'Lỗi OCR', INCORRECT_MATCH: 'Đánh giá tiêu chí sai',
  EMAIL_MATCH: 'Trùng email', PHONE_MATCH: 'Trùng số điện thoại', NAME_CONTENT_MATCH: 'Tên và nội dung nghề nghiệp tương đồng',
  STRONG_MATCH: 'Đáp ứng tốt', MATCH: 'Đáp ứng', UNCLEAR: 'Chưa rõ', NO_MATCH: 'Chưa đáp ứng',
  VERIFIED: 'Đã xác minh', FAILED: 'Chưa xác minh được', MANUAL_FIX: 'Đã sửa thủ công',
  EDUCATION: 'Học vấn', WORK_EXPERIENCE: 'Kinh nghiệm', SKILL: 'Kỹ năng',
  CERTIFICATION: 'Chứng chỉ', LANGUAGE: 'Ngôn ngữ', PROJECT: 'Dự án',
};
