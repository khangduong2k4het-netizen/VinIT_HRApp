/**
 * Vì sao một tệp bị từ chối — dịch sang việc HR phải làm.
 *
 * Backend ghi lý do bằng hai kiểu khác nhau: mã máy đọc được (`FILE_TOO_LARGE`)
 * và câu tiếng Anh do exception (`File bad.pdf is not a valid PDF or DOCX`).
 * Cả hai đều không được hiện nguyên văn: HR không cần biết exception, chỉ cần
 * biết nên làm gì tiếp. Hàm này thuần và phủ cả hai kiểu; kiểu lạ rơi về câu
 * trung tính, không bao giờ đoán bừa thành một nguyên nhân cụ thể.
 */
export type InvalidFileReason =
  | 'TOO_LARGE'
  | 'NOT_PDF_OR_DOCX'
  | 'EMPTY'
  | 'CREATED_APPLICATION'
  | 'UNKNOWN';

export function explainInvalidFile(errorCode?: string | null): InvalidFileReason {
  const code = String(errorCode || '').trim();
  if (!code) return 'UNKNOWN';
  if (/FILE_TOO_LARGE|SIZE/i.test(code)) return 'TOO_LARGE';
  // The validator distinguishes "empty or too large" in one sentence and
  // "not a valid PDF or DOCX" in another; size is checked first.
  if (/empty/i.test(code)) return 'EMPTY';
  if (/not a valid|Unsupported document type|PDF or DOCX/i.test(code)) return 'NOT_PDF_OR_DOCX';
  return 'UNKNOWN';
}
