import type { RankingItem } from '@/types';

export type ApplicantQueue =
  | 'ALL'
  | 'FILE_REVIEW'
  | 'DUPLICATE'
  | 'NEEDS_VERIFICATION'
  | 'POSSIBLE_MISMATCH'
  | 'NOT_ASSESSED'
  | 'MEETS_MANDATORY';

export type ApplicantSort = 'REVIEW_PRIORITY' | 'RANK' | 'SCORE_DESC' | 'COVERAGE_ASC' | 'NEWEST';

export interface ApplicantNavigationContext {
  positionId: string;
  queue: ApplicantQueue;
  sort: ApplicantSort;
  search: string;
  applicationIds: string[];
  storedAt: number;
}

export const APPLICANT_QUEUES: ApplicantQueue[] = [
  'ALL',
  'FILE_REVIEW',
  'DUPLICATE',
  'NEEDS_VERIFICATION',
  'POSSIBLE_MISMATCH',
  'NOT_ASSESSED',
  'MEETS_MANDATORY',
];

export const APPLICANT_SORTS: ApplicantSort[] = [
  'REVIEW_PRIORITY',
  'RANK',
  'SCORE_DESC',
  'COVERAGE_ASC',
  'NEWEST',
];

export function isApplicantQueue(value: string | null | undefined): value is ApplicantQueue {
  return !!value && APPLICANT_QUEUES.includes(value as ApplicantQueue);
}

export function isApplicantSort(value: string | null | undefined): value is ApplicantSort {
  return !!value && APPLICANT_SORTS.includes(value as ApplicantSort);
}

export function inScreening(status?: string) {
  return ['NEW', 'IN_REVIEW', 'SHORTLIST'].includes(status || '');
}

export function needsVerification(item: RankingItem) {
  return Boolean(
    item.needs_verification
    || item.matching_status === 'NEEDS_HR_VERIFICATION'
    || (item.evidence_coverage != null && item.evidence_coverage < 0.7),
  );
}

export function matchesApplicantQueue(item: RankingItem, queue: ApplicantQueue) {
  if (queue === 'ALL') return true;
  if (!inScreening(item.application_status)) return false;
  switch (queue) {
    case 'FILE_REVIEW':
      return item.file_processing_status === 'NEEDS_HR_REVIEW';
    case 'DUPLICATE':
      return Boolean(item.has_duplicate_warning);
    case 'NEEDS_VERIFICATION':
      return needsVerification(item);
    case 'POSSIBLE_MISMATCH':
      return Boolean(item.has_mismatch || item.matching_status === 'POSSIBLE_MISMATCH');
    case 'NOT_ASSESSED':
      return !item.matching_status || item.matching_status === 'NOT_ASSESSED';
    case 'MEETS_MANDATORY':
      return item.matching_status === 'MEETS_MANDATORY' && !item.has_mismatch && !needsVerification(item);
    default:
      return true;
  }
}

export function applicantQueueCounts(items: RankingItem[]) {
  const counts = Object.fromEntries(APPLICANT_QUEUES.map(queue => [queue, 0])) as Record<ApplicantQueue, number>;
  items.forEach(item => {
    counts.ALL += 1;
    APPLICANT_QUEUES.slice(1).forEach(queue => {
      if (matchesApplicantQueue(item, queue)) counts[queue] += 1;
    });
  });
  return counts;
}

function reviewPriority(item: RankingItem) {
  if (!inScreening(item.application_status)) return 6;
  if (item.file_processing_status === 'NEEDS_HR_REVIEW') return 0;
  if (item.has_duplicate_warning) return 1;
  if (needsVerification(item)) return 2;
  if (item.has_mismatch || item.matching_status === 'POSSIBLE_MISMATCH') return 3;
  if (!item.matching_status || item.matching_status === 'NOT_ASSESSED') return 4;
  return 5;
}

function compareNullableNumber(a: number | null | undefined, b: number | null | undefined, direction: 'asc' | 'desc') {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return direction === 'asc' ? a - b : b - a;
}

export function sortApplicantItems(items: RankingItem[], sort: ApplicantSort) {
  return [...items].sort((a, b) => {
    let result = 0;
    switch (sort) {
      case 'REVIEW_PRIORITY':
        result = reviewPriority(a) - reviewPriority(b)
          || compareNullableNumber(a.rank_number, b.rank_number, 'asc')
          || compareNullableNumber(a.matching_score, b.matching_score, 'desc');
        break;
      case 'RANK':
        result = compareNullableNumber(a.rank_number, b.rank_number, 'asc')
          || compareNullableNumber(a.matching_score, b.matching_score, 'desc');
        break;
      case 'SCORE_DESC':
        result = compareNullableNumber(a.matching_score, b.matching_score, 'desc')
          || compareNullableNumber(a.rank_number, b.rank_number, 'asc');
        break;
      case 'COVERAGE_ASC':
        result = compareNullableNumber(a.evidence_coverage, b.evidence_coverage, 'asc')
          || compareNullableNumber(a.matching_score, b.matching_score, 'desc');
        break;
      case 'NEWEST':
        result = String(b.created_at || '').localeCompare(String(a.created_at || ''))
          || compareNullableNumber(a.rank_number, b.rank_number, 'asc');
        break;
    }
    return result || String(a.candidate_name || '').localeCompare(String(b.candidate_name || ''));
  });
}

export function filterAndSortApplicantItems(items: RankingItem[], queue: ApplicantQueue, search: string, sort: ApplicantSort) {
  const normalizedSearch = search.trim().toLowerCase();
  const filtered = items.filter(item => {
    if (!matchesApplicantQueue(item, queue)) return false;
    return !normalizedSearch || String(item.candidate_name || '').toLowerCase().includes(normalizedSearch);
  });
  return sortApplicantItems(filtered, sort);
}

export function applicantNavigationKey(positionId: string) {
  return `hra-applicant-navigation:${positionId}`;
}

export function storeApplicantNavigation(context: ApplicantNavigationContext) {
  try {
    window.sessionStorage.setItem(applicantNavigationKey(context.positionId), JSON.stringify(context));
  } catch {
    // Navigation context is an enhancement; the list remains available without it.
  }
}

export function readApplicantNavigation(positionId: string): ApplicantNavigationContext | null {
  try {
    const raw = window.sessionStorage.getItem(applicantNavigationKey(positionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ApplicantNavigationContext;
    if (parsed.positionId !== positionId || !Array.isArray(parsed.applicationIds)) return null;
    return {
      ...parsed,
      queue: isApplicantQueue(parsed.queue) ? parsed.queue : 'ALL',
      sort: isApplicantSort(parsed.sort) ? parsed.sort : 'REVIEW_PRIORITY',
      search: parsed.search || '',
    };
  } catch {
    return null;
  }
}

/**
 * Merge the latest ranking with the position's applications, exactly as the applicants list shows them:
 * ranked rows still in screening keep their rank, and applications without an assessment are appended.
 */
export function mergeRankingWithApplications(ranks: RankingItem[], apps: any[], unnamedLabel: string): RankingItem[] {
  const appMap = new Map<string, any>();
  apps.forEach((a: any) => appMap.set(a.application_id, a));
  const merged: RankingItem[] = ranks
    .filter(r => inScreening(appMap.get(r.application_id)?.application_status))
    .map(r => {
      const a = appMap.get(r.application_id) || {};
      return {
        ...r,
        file_processing_status: a.file_processing_status,
        file_error: a.file_error,
        has_duplicate_warning: a.has_duplicate_warning,
        application_status: a.application_status,
        is_shortlisted: a.application_status === 'SHORTLIST',
        created_at: a.created_at,
      };
    });
  const rankedIds = new Set(merged.map(r => r.application_id));
  apps.forEach((a: any) => {
    if (rankedIds.has(a.application_id)) return;
    const identity = a.identity;
    let name = unnamedLabel;
    if (Array.isArray(identity) && identity[0]) name = identity[0].display_name || name;
    else if (identity && typeof identity === 'object') name = identity.display_name || name;
    merged.push({
      application_id: a.application_id,
      candidate_name: name,
      rank_number: null,
      matching_status: 'NOT_ASSESSED' as const,
      matching_score: null,
      evidence_coverage: null,
      needs_verification: false,
      has_mismatch: false,
      file_processing_status: a.file_processing_status,
      file_error: a.file_error,
      has_duplicate_warning: a.has_duplicate_warning,
      application_status: a.application_status,
      is_shortlisted: a.application_status === 'SHORTLIST',
      created_at: a.created_at,
    } as RankingItem);
  });
  return merged;
}
