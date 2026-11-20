/**
 * Lọc hồ sơ theo người phụ trách.
 *
 * Quyền vẫn do position_assignments quyết định; đây chỉ là "ai đang làm hồ sơ
 * nào", để hai HR cùng một vị trí không làm trùng hoặc cùng bỏ sót một hồ sơ.
 * Ba trạng thái đủ để trả lời câu hỏi thật của người dùng: việc của tôi, việc
 * chưa ai nhận, và mọi việc.
 */
export type ApplicantOwnership = 'ALL' | 'MINE' | 'UNASSIGNED';

export const APPLICANT_OWNERSHIP_FILTERS: ApplicantOwnership[] = ['ALL', 'MINE', 'UNASSIGNED'];

export function isApplicantOwnership(value: string | null | undefined): value is ApplicantOwnership {
  return !!value && APPLICANT_OWNERSHIP_FILTERS.includes(value as ApplicantOwnership);
}

type Owned = { assigned_to?: string | null };

export function matchesApplicantOwnership(
  item: Owned,
  filter: ApplicantOwnership,
  currentUserId?: string | null,
): boolean {
  const owner = item.assigned_to || null;
  if (filter === 'UNASSIGNED') return owner === null;
  if (filter === 'MINE') return Boolean(currentUserId) && owner === currentUserId;
  return true;
}

export function filterApplicantItemsByOwner<T extends Owned>(
  items: T[],
  filter: ApplicantOwnership,
  currentUserId?: string | null,
): T[] {
  if (filter === 'ALL') return items;
  return items.filter(item => matchesApplicantOwnership(item, filter, currentUserId));
}

export interface ApplicantOwnershipCounts {
  ALL: number;
  MINE: number;
  UNASSIGNED: number;
}

/** Đếm trên toàn bộ hồ sơ của vị trí, giống cách các chip hàng đợi đang đếm. */
export function applicantOwnershipCounts(
  items: Owned[],
  currentUserId?: string | null,
): ApplicantOwnershipCounts {
  const counts: ApplicantOwnershipCounts = { ALL: items.length, MINE: 0, UNASSIGNED: 0 };
  for (const item of items) {
    if (matchesApplicantOwnership(item, 'MINE', currentUserId)) counts.MINE += 1;
    if (matchesApplicantOwnership(item, 'UNASSIGNED', currentUserId)) counts.UNASSIGNED += 1;
  }
  return counts;
}
