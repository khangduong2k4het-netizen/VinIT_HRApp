/**
 * Ghi chú HR gắn với tiêu chí.
 *
 * Ghi chú chung ở cuối trang đúng cho nhận xét về cả hồ sơ, nhưng câu "tiêu chí 3
 * nói có chứng chỉ X, tôi thấy không đúng" chỉ có nghĩa khi nằm cạnh tiêu chí 3.
 * Hàm ở đây chỉ phân loại, không quyết định gì: ghi chú vẫn append-only và vẫn
 * thuộc về người viết.
 */
import type { PrivateNote } from '@/types';

/** Ghi chú của một tiêu chí, mới nhất trước (API đã trả theo thứ tự đó). */
export function notesForCriterion(notes: PrivateNote[], criterionId: string): PrivateNote[] {
  if (!criterionId) return [];
  return notes.filter(note => note.criterion_id === criterionId);
}

/** Ghi chú chung của hồ sơ — thứ hiển thị trong bảng ghi chú ở cuối trang. */
export function generalNotes(notes: PrivateNote[]): PrivateNote[] {
  return notes.filter(note => !note.criterion_id);
}

export interface CriterionNoteSummary {
  total: number;
  /** Số tiêu chí có ít nhất một ghi chú. */
  criteriaWithNotes: number;
}

export function summarizeCriterionNotes(notes: PrivateNote[]): CriterionNoteSummary {
  const criteria = new Set<string>();
  for (const note of notes) {
    if (note.criterion_id) criteria.add(note.criterion_id);
  }
  return { total: notes.length, criteriaWithNotes: criteria.size };
}
