/**
 * Quyết định phải làm gì khi lời gọi sinh tiêu chí không trả về kết quả dùng được.
 *
 * Vì sao cần: quá trình sinh tiêu chí chạy LLM ngay trong request HTTP. Request
 * đó có thể bị cắt giữa đường (proxy của hosting, Cloudflare, mất mạng) — không
 * phải backend trả lỗi. Khi bị cắt, browser nhận một response KHÔNG có trường
 * ``detail``. Nếu ta coi đó là thất bại rồi bảo HR "chưa tạo được tiêu chí",
 * trong khi backend vẫn chạy xong và đã lưu tiêu chí, thì thông báo là sai và
 * HR sẽ tưởng phải làm lại.
 *
 * Nên: khi không đọc được lý do từ backend, phải KIỂM TRA LẠI bằng một request
 * đọc dữ liệu (GET versions) thay vì đoán.
 */

export type GenerationFailureKind =
  /** Backend trả JSON có ``detail``: đây là lỗi thật, hiển thị nguyên văn. */
  | 'server'
  /** Không có response (mất mạng); không biết phía server đã chạy chưa. */
  | 'network'
  /** Có response nhưng không có ``detail``: proxy cắt, 500 plain text, HTML. */
  | 'opaque';

export type GenerationOutcome =
  /** Tiêu chí đã có trên server: mở vị trí luôn. */
  | { action: 'verified' }
  /** Thử lại được, và có thông điệp cụ thể cho HR. */
  | { action: 'retry'; kind: GenerationFailureKind; detail: string }
  /** Không kiểm chứng được: phải cho HR tự chọn, không tự đoán. */
  | { action: 'unknown'; kind: GenerationFailureKind };

/**
 * Đọc lỗi từ một exception axios và phân loại theo mức độ biết được sự thật.
 *
 * @param error lỗi axios (hoặc bất cứ thứ gì bị ném ra)
 * @param hasCriteria kết quả GET versions sau lỗi (``null`` nếu không kiểm tra được)
 */
export function interpretGenerationFailure(error: any, hasCriteria: boolean | null): GenerationOutcome {
  const response = error?.response;
  const detail = typeof response?.data?.detail === 'string' ? response.data.detail.trim() : '';
  const kind: GenerationFailureKind = detail ? 'server' : response ? 'opaque' : 'network';
  // Đã kiểm tra và thấy có tiêu chí: request hỏng ở đường truyền chứ server
  // vẫn lưu xong. Coi như thành công để HR không làm lại việc đã xong.
  if (hasCriteria === true) return { action: 'verified' };
  if (detail) return { action: 'retry', kind, detail };
  // Kiểm tra được và chắc chắn chưa có tiêu chí -> thử lại là hợp lý.
  if (hasCriteria === false) return { action: 'retry', kind, detail: '' };
  // Không kiểm tra được (offline, GET cũng lỗi): không được khẳng định là
  // "chưa tạo được", vì có thể tiêu chí đã lưu.
  return { action: 'unknown', kind };
}
