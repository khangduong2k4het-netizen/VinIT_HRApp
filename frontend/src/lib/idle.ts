/**
 * Hoãn việc không cần cho màn hình đầu.
 *
 * Trang hồ sơ gọi vài thứ chỉ để hoàn thiện giao diện (bộ đếm hàng đợi, badge
 * việc đang chờ, prefetch hồ sơ kế). Gọi chúng ngay lúc mở trang thì chúng tranh
 * băng thông và cả băng thông CPU với hồ sơ + tiêu chí — hai thứ HR thật sự cần
 * trước. `requestIdleCallback` để trình duyệt tự chọn lúc rảnh; nơi không có API
 * này thì lùi về một timeout ngắn thay vì bỏ hẳn việc.
 *
 * Trả về hàm huỷ để effect dọn dẹp được khi rời trang trước lúc việc chạy.
 */
export function runWhenIdle(task: () => void, timeoutMs = 1500): () => void {
  if (typeof window === 'undefined') return () => {};
  const withIdle = window as unknown as {
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
    cancelIdleCallback?: (handle: number) => void;
  };
  if (typeof withIdle.requestIdleCallback === 'function') {
    const handle = withIdle.requestIdleCallback(() => task(), { timeout: timeoutMs });
    return () => withIdle.cancelIdleCallback?.(handle);
  }
  const handle = window.setTimeout(task, 100);
  return () => window.clearTimeout(handle);
}
