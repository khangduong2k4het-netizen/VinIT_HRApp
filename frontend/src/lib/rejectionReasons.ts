/**
 * Lý do loại hồ sơ: nhớ lý do đã dùng và gợi ý câu từ tiêu chí chưa đạt.
 *
 * HR loại hàng chục hồ sơ mỗi ngày với gần như cùng một lý do. Gõ lại từ đầu vừa
 * chậm vừa sinh lý do viết tắt ("ko đủ KN"), làm lịch sử quyết định khó đọc cho
 * người mở hồ sơ sau. Hai nguồn gợi ý ở đây đều không tự quyết định thay HR:
 * bấm một gợi ý là điền vào ô nhập, sửa được như chữ tự gõ.
 *
 * Lý do đã dùng lưu trong localStorage của chính trình duyệt, cùng chỗ và cùng
 * lý do với số đo UX: không gửi lên máy chủ, không ghi tên hay nội dung hồ sơ.
 */
import type { Criterion, CriterionResult, RequirementSpec } from '@/types';

export const REJECTION_REASONS_KEY_PREFIX = 'hra-rejection-reasons';
export const REJECTION_REASONS_MAX = 20;
export const REJECTION_REASON_MAX_LENGTH = 1000;

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

function browserStorage(): StorageLike | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

export function rejectionReasonsKey(positionId: string): string {
  return `${REJECTION_REASONS_KEY_PREFIX}:${positionId}`;
}

/** Khoảng trắng thừa và xuống dòng làm hai lý do giống nhau thành hai mục khác nhau. */
export function normalizeReason(value: string): string {
  return value.trim().replace(/\s+/g, ' ').slice(0, REJECTION_REASON_MAX_LENGTH);
}

function dedupeReasons(reasons: string[]): string[] {
  const seen = new Set<string>();
  const kept: string[] = [];
  for (const reason of reasons) {
    const normalized = normalizeReason(reason);
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    kept.push(normalized);
  }
  return kept;
}

/** Lý do đã dùng cho vị trí này, mới nhất trước. Dữ liệu hỏng bị bỏ qua. */
export function readRecentReasons(
  positionId: string,
  storage: StorageLike | null = browserStorage(),
): string[] {
  if (!storage) return [];
  try {
    const raw = storage.getItem(rejectionReasonsKey(positionId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return dedupeReasons(parsed.filter((value): value is string => typeof value === 'string'))
      .slice(0, REJECTION_REASONS_MAX);
  } catch {
    return [];
  }
}

/**
 * Ghi nhớ một lý do. Lưu cả khi storage lỗi thì chỉ là mất gợi ý lần sau, không
 * được làm hỏng thao tác đổi trạng thái.
 */
export function rememberReason(
  positionId: string,
  reason: string,
  storage: StorageLike | null = browserStorage(),
): string[] {
  const normalized = normalizeReason(reason);
  if (!storage || !normalized) return readRecentReasons(positionId, storage);
  const next = dedupeReasons([normalized, ...readRecentReasons(positionId, storage)])
    .slice(0, REJECTION_REASONS_MAX);
  try {
    storage.setItem(rejectionReasonsKey(positionId), JSON.stringify(next));
  } catch {
    // Không lưu được: gợi ý lần sau sẽ thiếu, quyết định vẫn đã được gửi.
  }
  return next;
}

export interface CriterionReasonCandidate {
  criterion_id: string;
  /** Tên tiêu chí để người đọc hiểu gợi ý nói về điều gì. */
  name: string;
  outcome: 'NO_MATCH' | 'UNCLEAR';
  /** Đặc tả yêu cầu, nếu có — nơi sinh ra câu "≥ 3 năm Python". */
  spec: RequirementSpec | null;
}

/**
 * Gợi ý chỉ đến từ tiêu chí **bắt buộc** đã trượt hoặc chưa đủ bằng chứng: đó là
 * lý do loại thật, không phải suy diễn. Tiêu chí ưu tiên đạt hay trượt đều không
 * phải lý do loại hồ sơ, nên không xuất hiện để tránh tạo lý do vô nghĩa.
 */
export function criterionReasonCandidates(
  criteria: Criterion[],
  results: CriterionResult[],
  limit = 3,
): CriterionReasonCandidate[] {
  const byId = new Map(criteria.map(criterion => [criterion.criterion_id, criterion]));
  const seen = new Set<string>();
  const candidates: CriterionReasonCandidate[] = [];
  for (const result of results) {
    if (result.category !== 'MUST_HAVE') continue;
    if (result.outcome !== 'NO_MATCH' && result.outcome !== 'UNCLEAR') continue;
    if (seen.has(result.criterion_id)) continue;
    const criterion = byId.get(result.criterion_id);
    const name = (criterion?.name || result.criterion_name || '').trim();
    if (!name) continue;
    seen.add(result.criterion_id);
    candidates.push({
      criterion_id: result.criterion_id,
      name,
      outcome: result.outcome,
      spec: criterion?.requirement_spec ?? null,
    });
    if (candidates.length >= limit) break;
  }
  return candidates;
}
