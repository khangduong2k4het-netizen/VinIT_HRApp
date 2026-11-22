'use client';

import { applicationsApi } from '@/lib/api';
import type { ApplicationWithAssessment } from '@/types';

/**
 * Dữ liệu hồ sơ kế tiếp, tải trước khi HR còn đang đọc hồ sơ hiện tại.
 *
 * Route của hồ sơ kế đã được `next/link` prefetch khi link nằm trong khung nhìn,
 * nhưng thứ chặn lần vẽ đầu của trang hồ sơ không phải route mà là
 * `GET /v1/applications/{id}`: trang hiện spinner cho tới khi request đó xong.
 * Tải trước chính request này thì lần bấm `n` / "Hồ sơ tiếp theo" vẽ được ngay.
 *
 * Chỉ giữ trong bộ nhớ của tab này, một hồ sơ một mục, và chỉ dùng một lần: trang
 * hồ sơ lấy bản đã tải trước để vẽ, rồi vẫn gọi lại API để không hiển thị dữ liệu
 * cũ nếu hồ sơ vừa đổi ở nơi khác. Dữ liệu quá cũ thì bỏ, không dùng.
 */
const FRESH_MS = 60_000;

type Entry = {
  at: number;
  value: ApplicationWithAssessment | null;
  settled: boolean;
  promise: Promise<ApplicationWithAssessment | null>;
};

const entries = new Map<string, Entry>();

/** Bắt đầu tải hồ sơ; gọi lại khi đang tải thì dùng chung một request. */
export function prefetchApplication(applicantId: string): Promise<ApplicationWithAssessment | null> {
  const existing = entries.get(applicantId);
  if (existing && Date.now() - existing.at < FRESH_MS) return existing.promise;
  const entry: Entry = { at: Date.now(), value: null, settled: false, promise: Promise.resolve(null) };
  entry.promise = applicationsApi.getById(applicantId)
    // Không có quyền, hồ sơ đã bị xoá, mạng lỗi: việc tải trước thất bại không
    // được làm hỏng gì — trang hồ sơ sẽ tự gọi lại và hiện lỗi như thường.
    .then(response => response.data as ApplicationWithAssessment)
    .catch(() => null)
    .then(value => {
      entry.value = value;
      entry.settled = true;
      return value;
    });
  entries.set(applicantId, entry);
  return entry.promise;
}

/**
 * Bản đã tải trước, chỉ khi request đã xong và còn mới. Lấy ra là xoá khỏi bộ nhớ:
 * mỗi lần mở hồ sơ chỉ được dùng một lần, lần sau phải là dữ liệu mới.
 */
export function takePrefetchedApplication(applicantId: string): ApplicationWithAssessment | null {
  const entry = entries.get(applicantId);
  if (!entry) return null;
  entries.delete(applicantId);
  if (!entry.settled || Date.now() - entry.at > FRESH_MS) return null;
  return entry.value;
}
