import type { ApplicantOwnership } from './applicantOwnership';

/**
 * Nhãn chip lọc theo người phụ trách, tách khỏi component để dùng chung và để
 * i18n quét được như mọi nhãn khác.
 */
export const APPLICANT_OWNERSHIP_LABELS: Record<ApplicantOwnership, string> = {
  ALL: 'Mọi người phụ trách',
  MINE: 'Của tôi',
  UNASSIGNED: 'Chưa ai nhận',
};
