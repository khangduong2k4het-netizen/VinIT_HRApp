/**
 * File `.ics` cho một buổi phỏng vấn — để người phỏng vấn bỏ vào lịch của họ.
 *
 * Vì sao ở client, không ở backend: đây là một phép biến đổi dữ liệu đã có
 * thành định dạng văn bản, không cần quyền mới và không đụng DB. Làm ở client
 * thì không phải thêm endpoint nào phải bảo vệ.
 *
 * Ba chi tiết dễ sai và đều đã xử lý:
 *
 * 1. **CRLF**: RFC 5545 bắt buộc `\r\n`. Nhiều ứng dụng lịch vẫn đọc được `\n`,
 *    nhưng Apple Calendar thì không — và lỗi hiện ra là "file không hợp lệ",
 *    không chỉ ra dòng nào.
 * 2. **Gấp dòng ở 75 octet**: dòng dài phải xuống dòng bằng một khoảng trắng ở
 *    đầu dòng tiếp theo. Tên buổi tiếng Việt dài và có dấu là ca dễ vượt.
 * 3. **Thoát ký tự**: dấu phẩy, chấm phẩy, backslash và xuống dòng trong phần
 *    mô tả phải escape, nếu không ứng dụng lịch cắt câu ở giữa.
 */

import type { Interview } from '@/components/positions/InterviewPanel';

const LOCATION_LABEL: Record<string, string> = {
  ONSITE: 'Tại văn phòng',
  ONLINE: 'Trực tuyến',
  PHONE: 'Qua điện thoại',
};

/** `2026-12-01T07:00:00Z` → `20261201T070000Z` (UTC, đúng như RFC yêu cầu). */
export function icsStamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

/** Escape theo RFC 5545 §3.3.11. */
export function icsEscape(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

/**
 * Gấp dòng ở 75 octet, dòng nối bắt đầu bằng một khoảng trắng.
 *
 * Phải gấp theo **ký tự**, không theo byte: cắt ở ranh giới byte thứ 73 sẽ chẻ
 * đôi một ký tự UTF-8 nhiều byte, và kết quả là file hỏng đúng ở những chỗ có
 * dấu tiếng Việt — tức là gần như mọi tên ứng viên.
 *
 * Giới hạn 75 octet là giới hạn thật của RFC; kiểm bằng `Buffer.byteLength` sau
 * khi gấp chứ không đoán.
 */
export function icsFold(line: string): string {
  if (Buffer.byteLength(line, 'utf8') <= 75) return line;
  const parts: string[] = [];
  let current = '';
  for (const char of line) {          // lặp theo code point, không theo byte
    // 73 chứ không 75: dòng nối có thêm một khoảng trắng ở đầu.
    if (Buffer.byteLength(current + char, 'utf8') > 73) {
      parts.push(current);
      current = char;
    } else {
      current += char;
    }
  }
  if (current) parts.push(current);
  return parts.join('\r\n ');
}

export function buildInterviewIcs(interview: Interview, now = new Date()): string {
  const title = `Phỏng vấn vòng ${interview.round_number}`
    + (interview.candidate_name ? ` — ${interview.candidate_name}` : '')
    + (interview.position_code ? ` (${interview.position_code})` : '');
  const description = [
    interview.position_title,
    interview.location_text ? `Địa điểm: ${interview.location_text}` : null,
    'Giờ hiển thị theo giờ Việt Nam (GMT+7).',
  ].filter(Boolean).join('\n');
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//VinIT HRApp//Interviews//VI',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    // UID ổn định theo buổi: nhập lại cùng buổi thì ứng dụng lịch cập nhật thay
    // vì tạo bản trùng.
    `UID:${interview.interview_id}@vinit-hrapp`,
    `DTSTAMP:${icsStamp(now.toISOString())}`,
    `DTSTART:${icsStamp(interview.starts_at)}`,
    `DTEND:${icsStamp(interview.ends_at)}`,
    `SUMMARY:${icsEscape(title)}`,
    `DESCRIPTION:${icsEscape(description)}`,
    `LOCATION:${icsEscape(interview.location_text || LOCATION_LABEL[interview.location_kind] || '')}`,
    'STATUS:CONFIRMED',
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  return lines.map(icsFold).join('\r\n') + '\r\n';
}
