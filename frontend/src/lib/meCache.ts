'use client';

import { authApi } from '@/lib/api';

/**
 * Hồ sơ tài khoản hiện tại, dùng chung giữa các nơi cùng hỏi trong một tab.
 *
 * `GET /v1/auth/me` không đổi giữa hai lần bấm `n` liên tiếp, nhưng trước đây
 * mỗi lần chuyển hồ sơ lại hỏi **hai** lần: khung trang kiểm tra lại quyền khi
 * `pathname` đổi, và trang hồ sơ tự hỏi để biết mình là ai (trang được gắn lại
 * theo từng `applicantId`). Đo được hai request cách nhau 40–60 ms, cùng một
 * câu trả lời.
 *
 * Cửa sổ ngắn (30 giây) chứ không phải cache vĩnh viễn: quyền và trạng thái
 * "phải đổi mật khẩu" vẫn được đọc lại trong vòng nửa phút, nên thay đổi quyền
 * phía máy chủ không bị giữ quá lâu. Bản ghi gắn với token đang dùng — đăng
 * xuất rồi đăng nhập tài khoản khác là token khác, nên không thể đọc nhầm hồ sơ
 * của người trước. Request đang bay được dùng chung; lỗi thì bỏ khỏi bộ nhớ để
 * lần sau thử lại.
 */
export const ME_TTL_MS = 30_000;

// Danh tính đã tải gần nhất, để nơi khác đọc mà không phải hỏi lại. Khung trang
// là nơi duy nhất gọi `auth/me`; trang hồ sơ chỉ cần `user_id` để hiện người phụ
// trách, nên đọc bản này thay vì tự hỏi mỗi lần được gắn lại (mỗi hồ sơ).
type Snapshot = { token: string | null; user: CurrentUser };
let snapshot: Snapshot | null = null;
const listeners = new Set<(user: CurrentUser) => void>();

export function getCachedUser(): CurrentUser | null {
  if (!snapshot || snapshot.token !== readToken()) return null;
  return snapshot.user;
}

export function subscribeCurrentUser(listener: (user: CurrentUser) => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function publish(token: string | null, user: CurrentUser) {
  snapshot = { token, user };
  listeners.forEach(listener => listener(user));
}

export type CurrentUser = {
  user_id?: string;
  email?: string;
  display_name?: string;
  must_change_password?: boolean;
  system_roles?: string[];
  position_assignments?: { position_id: string; position_role: string }[];
};

type Entry = { at: number; token: string | null; promise: Promise<CurrentUser> };

let entry: Entry | null = null;

function readToken(): string | null {
  return typeof window === 'undefined' ? null : localStorage.getItem('hra_access_token');
}

export function getCurrentUser(): Promise<CurrentUser> {
  const token = readToken();
  if (entry && entry.token === token && Date.now() - entry.at < ME_TTL_MS) return entry.promise;
  const next: Entry = { at: Date.now(), token, promise: Promise.resolve({}) };
  next.promise = authApi.me()
    .then(response => {
      const user = (response.data || {}) as CurrentUser;
      publish(token, user);
      return user;
    })
    .catch(error => {
      if (entry === next) entry = null;
      throw error;
    });
  entry = next;
  return next.promise;
}
