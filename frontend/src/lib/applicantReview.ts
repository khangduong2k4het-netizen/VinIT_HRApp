import type { RankingItem } from '@/types';
import { WORK_CONCEPT_LABELS } from './workVocabulary';

/**
 * Evidence coverage under this value means the assessment is not solid enough to
 * rank. Mirrors `MIN_EVIDENCE_COVERAGE` in backend/app/core/config.py — keep the
 * two in step until the API returns the threshold in its payload.
 */
export const COVERAGE_THRESHOLD = 0.7;

/**
 * Applications still in the screening stage. Everything else (rejected,
 * interviewed, offered) is history, not work left to do, so the queue chips and
 * their counts ignore it. Mirrors `SCREENING_APPLICATION_STATUSES` in
 * backend/app/services/workspace.py.
 */
export const SCREENING_STATUSES = ['NEW', 'IN_REVIEW', 'SHORTLIST'];

export type ApplicantQueue =
  | 'ALL'
  | 'SHORTLIST'
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
  /** Where the list was scrolled to, so returning from a profile lands in place. */
  scrollY?: number;
}

export const APPLICANT_QUEUES: ApplicantQueue[] = [
  'ALL',
  'SHORTLIST',
  'FILE_REVIEW',
  'DUPLICATE',
  'NEEDS_VERIFICATION',
  'POSSIBLE_MISMATCH',
  'NOT_ASSESSED',
  'MEETS_MANDATORY',
];

/**
 * Vietnamese labels shared by the filter chips, the result summary and the
 * Dashboard work queue (see lib/workVocabulary.ts). One wording per concept.
 */
export const APPLICANT_QUEUE_LABELS: Record<ApplicantQueue, string> = {
  ALL: 'Tất cả',
  SHORTLIST: WORK_CONCEPT_LABELS.SHORTLIST,
  FILE_REVIEW: WORK_CONCEPT_LABELS.FILE_REVIEW,
  NEEDS_VERIFICATION: WORK_CONCEPT_LABELS.NEEDS_VERIFICATION,
  DUPLICATE: WORK_CONCEPT_LABELS.DUPLICATE,
  POSSIBLE_MISMATCH: WORK_CONCEPT_LABELS.POSSIBLE_MISMATCH,
  NOT_ASSESSED: WORK_CONCEPT_LABELS.NOT_ASSESSED,
  MEETS_MANDATORY: WORK_CONCEPT_LABELS.MEETS_MANDATORY,
};

export const APPLICANT_SORTS: ApplicantSort[] = [
  'REVIEW_PRIORITY',
  'RANK',
  'SCORE_DESC',
  'COVERAGE_ASC',
  'NEWEST',
];

/**
 * Queue codes in URLs are UPPER_SNAKE (`?queue=FILE_REVIEW`). Work-queue deep
 * links used to be emitted lower-case, and older links may still be in
 * bookmarks, so accept both rather than dropping the filter on the floor.
 */
export function normalizeApplicantQueue(value: string | null | undefined): ApplicantQueue | null {
  if (!value) return null;
  const candidate = value.trim().toUpperCase();
  return (APPLICANT_QUEUES as string[]).includes(candidate) ? (candidate as ApplicantQueue) : null;
}

export function isApplicantQueue(value: string | null | undefined): value is ApplicantQueue {
  return normalizeApplicantQueue(value) !== null;
}

export function isApplicantSort(value: string | null | undefined): value is ApplicantSort {
  return !!value && APPLICANT_SORTS.includes(value as ApplicantSort);
}

export function inScreening(status?: string) {
  return SCREENING_STATUSES.includes(status || '');
}

export function needsVerification(item: RankingItem) {
  // Never-assessed rows have no score to verify. They belong to the
  // "not assessed" queue only; counting them here made one application show up
  // in two queues and made the dashboard figure impossible to reconcile.
  if (!item.matching_status || item.matching_status === 'NOT_ASSESSED') return false;
  return Boolean(
    item.needs_verification
    || item.matching_status === 'NEEDS_HR_VERIFICATION'
    || (item.evidence_coverage != null && item.evidence_coverage < COVERAGE_THRESHOLD),
  );
}

/** A row that was never assessed has no rank, whatever the queue says. */
export function isAssessed(item: RankingItem) {
  return Boolean(item.matching_status && item.matching_status !== 'NOT_ASSESSED');
}

export function matchesApplicantQueue(item: RankingItem, queue: ApplicantQueue) {
  if (queue === 'ALL') return true;
  if (!inScreening(item.application_status)) return false;
  switch (queue) {
    case 'SHORTLIST':
      return item.application_status === 'SHORTLIST';
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

/** Query string for a ranking URL, omitting defaults so links stay readable. */
export function applicantSearchParams(queue: ApplicantQueue, sort: ApplicantSort, search: string) {
  const params = new URLSearchParams();
  if (queue !== 'ALL') params.set('queue', queue);
  if (sort !== 'RANK' || (queue !== 'ALL' && queue !== 'SHORTLIST')) params.set('sort', sort);
  if (search.trim()) params.set('q', search.trim());
  return params;
}

/** Ranking URL that carries the browse context, used by every link into a profile. */
export function applicantListHref(positionId: string, queue: ApplicantQueue, sort: ApplicantSort, search: string) {
  const query = applicantSearchParams(queue, sort, search).toString();
  return `/positions/${positionId}/applicants${query ? `?${query}` : ''}`;
}

/** Profile URL that keeps the queue/sort/search context in the URL itself. */
export function applicantProfileHref(positionId: string, applicationId: string, queue: ApplicantQueue, sort: ApplicantSort, search: string) {
  const query = applicantSearchParams(queue, sort, search).toString();
  return `/positions/${positionId}/applicants/${applicationId}${query ? `?${query}` : ''}`;
}

/** Read queue/sort/search from a profile URL so a deep link keeps its filter. */
export function readApplicantSearchParams(search: string) {
  const params = new URLSearchParams(search);
  return {
    queue: normalizeApplicantQueue(params.get('queue')),
    sort: isApplicantSort(params.get('sort')) ? (params.get('sort') as ApplicantSort) : null,
    search: params.get('q') || '',
  };
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
      queue: normalizeApplicantQueue(parsed.queue) || 'ALL',
      sort: isApplicantSort(parsed.sort) ? parsed.sort : 'RANK',
      search: parsed.search || '',
      scrollY: typeof parsed.scrollY === 'number' && parsed.scrollY > 0 ? parsed.scrollY : 0,
    };
  } catch {
    return null;
  }
}

/**
 * Bounded rendering window for long applicant queues. Returns the slice that is
 * mounted plus whether more rows exist; it never changes order or ranks.
 */
export function windowApplicantItems<T>(items: T[], limit: number, step = 50) {
  const safeLimit = Math.max(step, Math.floor(limit / step) * step);
  return { visible: items.slice(0, safeLimit), hasMore: items.length > safeLimit, nextLimit: safeLimit + step, total: items.length };
}

/**
 * How long an application has been waiting, in whole days.
 * Returns null when the timestamp is missing or unparseable, so the UI can stay
 * silent instead of inventing "0 ngày" for rows it knows nothing about.
 */
export function daysWaiting(createdAt: string | null | undefined, now: Date = new Date()) {
  if (!createdAt) return null;
  const started = new Date(createdAt).getTime();
  if (Number.isNaN(started)) return null;
  const elapsed = now.getTime() - started;
  if (elapsed < 0) return null;
  return Math.floor(elapsed / 86_400_000);
}

/** Waiting long enough to deserve a prompt, but never a reason to reorder ranks. */
export const WAITING_ATTENTION_DAYS = 7;
