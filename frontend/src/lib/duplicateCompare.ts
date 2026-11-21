/**
 * Hai hồ sơ bị gắn cờ trùng phải được nhìn cạnh nhau.
 *
 * Trước đây muốn đối chiếu, HR mở hồ sơ A, ghi nhớ vài dòng, quay lại danh sách,
 * mở hồ sơ B rồi so trong đầu — với dữ liệu định danh, CV và cả bốn tiêu chí.
 * Module này giữ phần thuần của màn so sánh: đường dẫn tới màn đó, nhãn loại tín
 * hiệu trùng, và việc tìm đúng tín hiệu của cặp đang xem (một vị trí có thể có
 * nhiều cặp trùng).
 */
export interface DuplicateSignalLike {
  signal_type?: string | null;
  application_id_1: string;
  application_id_2: string;
}

/** Loại tín hiệu do bộ dò trả về; lạ thì hiển thị nguyên mã, không đoán nghĩa. */
export const DUPLICATE_SIGNAL_LABELS: Record<string, string> = {
  SAME_EMAIL: 'Cùng email',
  SAME_PHONE: 'Cùng số điện thoại',
  SAME_NAME: 'Cùng họ tên',
  SAME_NAME_AND_EMAIL: 'Cùng họ tên và email',
};

/** Màn so sánh giữ nguyên cặp đang xem trong URL để mở lại/tải lại vẫn đúng cặp. */
export function duplicateCompareHref(positionId: string, leftId: string, rightId: string): string {
  const search = new URLSearchParams({ left: leftId, right: rightId });
  return `/positions/${positionId}/applicants/compare?${search.toString()}`;
}

/**
 * Tín hiệu nói về đúng cặp này, không phân biệt bên trái/bên phải: thứ tự hai
 * application trong bảng tín hiệu do bộ dò quyết định, không do màn hình.
 */
export function pairSignal<T extends DuplicateSignalLike>(signals: T[], a: string | null | undefined, b: string | null | undefined): T | undefined {
  if (!a || !b) return undefined;
  return signals.find(signal => (signal.application_id_1 === a && signal.application_id_2 === b)
    || (signal.application_id_1 === b && signal.application_id_2 === a));
}

/** Số tiêu chí hai bên kết luận khác nhau — phần đáng đọc nhất của màn so sánh. */
export function differingOutcomes<T extends { criterion_id: string; outcome: string }>(left: T[], right: T[]): string[] {
  return left
    .filter(item => {
      const other = right.find(candidate => candidate.criterion_id === item.criterion_id);
      return Boolean(other) && other!.outcome !== item.outcome;
    })
    .map(item => item.criterion_id);
}
