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
 * Chỉ giữ trong bộ nhớ của tab này, một hồ sơ một mục, và chỉ dùng một lần. Dữ
 * liệu quá cũ thì bỏ, không dùng.
 *
 * **Không luôn đọc lại API.** Trước đây trang hồ sơ vẽ từ bản tải trước rồi vẫn
 * gọi `GET /applications/{id}` ngay sau đó, nên mỗi lần mở hồ sơ kế tốn hai
 * request cho cùng một dữ liệu vừa tải xong vài trăm ms trước. Nay bản tải trước
 * vừa xong trong `PREFETCH_REUSE_MS` được dùng luôn, không xác nhận lại; chỉ bản
 * đã cũ hơn cửa sổ đó mới đọc lại từ API (vẫn vẽ ngay bằng bản tải trước).
 */
const FRESH_MS = 60_000;

/**
 * Cửa sổ coi bản tải trước là "vừa xong": trong khoảng này, đọc lại API chỉ lặp
 * lại đúng dữ liệu vừa tải, nên bỏ qua. Đủ ngắn để không giữ một quyết định cũ
 * khi HR đọc hồ sơ lâu, đủ dài để không phạt cú bấm ngay sau khi tải trước.
 */
export const PREFETCH_REUSE_MS = 5_000;

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
 *
 * `fresh` nghĩa là bản này vừa xong trong `PREFETCH_REUSE_MS`, nên trang hồ sơ
 * được phép vẽ bằng nó mà không cần gọi lại API để xác nhận.
 */
export function takePrefetchedApplication(
  applicantId: string,
): { data: ApplicationWithAssessment; fresh: boolean } | null {
  const entry = entries.get(applicantId);
  if (!entry) return null;
  entries.delete(applicantId);
  const ageMs = Date.now() - entry.at;
  if (!entry.settled || ageMs > FRESH_MS || !entry.value) return null;
  return { data: entry.value, fresh: ageMs <= PREFETCH_REUSE_MS };
}
