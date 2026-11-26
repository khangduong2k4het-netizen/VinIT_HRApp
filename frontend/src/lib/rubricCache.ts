'use client';

import { criteriaApi } from '@/lib/api';
import type { Criterion } from '@/types';

/**
 * Rubric đã duyệt của một vị trí, dùng chung giữa các lần mở hồ sơ.
 *
 * Trang hồ sơ cần rubric để trả lời "tiêu chí này yêu cầu gì", nhưng rubric thuộc
 * về **vị trí**, không thuộc hồ sơ: bấm `n` sang hồ sơ kế trong cùng vị trí không
 * làm nó đổi. Trước đây mỗi lần mở hồ sơ là một
 * `GET /v1/criteria/position/{id}/approved` lặp lại y hệt.
 *
 * Cửa sổ ngắn (60 giây) để thay đổi rubric ở nơi khác vẫn tới được trang mà không
 * phải tải lại; request đang bay được dùng chung nên hai lần gọi sát nhau không
 * nhân đôi. Lỗi thì bỏ khỏi bộ nhớ để lần mở sau thử lại.
 */
export const RUBRIC_TTL_MS = 60_000;

type Entry = { at: number; promise: Promise<Criterion[]> };

const entries = new Map<string, Entry>();

export function getApprovedRubric(positionId: string): Promise<Criterion[]> {
  const existing = entries.get(positionId);
  if (existing && Date.now() - existing.at < RUBRIC_TTL_MS) return existing.promise;
  const entry: Entry = { at: Date.now(), promise: Promise.resolve([]) };
  entry.promise = criteriaApi.getApproved(positionId)
    .then(response => (response.data?.criteria || []) as Criterion[])
    .catch(error => {
      entries.delete(positionId);
      throw error;
    });
  entries.set(positionId, entry);
  return entry.promise;
}
