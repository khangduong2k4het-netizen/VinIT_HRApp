'use client';
/**
 * Một chỗ duy nhất để nói "đã xong" hoặc "không xong" sau một thao tác async.
 *
 * Trước đây ba luồng cùng loại có ba kiểu phản hồi khác nhau: đổi trạng thái hồ
 * sơ hiện Snackbar, lưu scorecard thì im lặng (chỉ đổi nhãn nút), chia sẻ
 * shortlist thì hiện Snackbar không có vùng thông báo. Toàn app chỉ có 5 chỗ có
 * `aria-live`, nghĩa là phần lớn thông báo thành công không được đọc lên.
 *
 * Vì sao không dùng <Snackbar> của MUI: MUI chỉ mount nội dung khi `open` là
 * true. Một live region sinh ra cùng lúc với thông báo thì nhiều screen reader
 * bỏ qua, vì chúng theo dõi vùng đó từ trước. Ở đây vùng thông báo LUÔN có mặt
 * trong DOM, rỗng khi không có gì — chỉ nội dung bên trong thay đổi.
 *
 * Hai nguyên tắc:
 *  - Thành công: tự tắt, `role="status"` + `aria-live="polite"` (không cắt ngang).
 *  - Lỗi: KHÔNG tự tắt. Lỗi là việc HR phải xử lý; nó tự biến mất sau vài giây là
 *    cách chắc chắn nhất để người dùng bỏ lỡ nó.
 */
import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import { useI18n } from '@/i18n/I18nProvider';

export interface ActionFeedbackProps {
  /** Message to announce on success; falsy means nothing to say. */
  success?: string | null;
  onSuccessClose?: () => void;
  /** Message to show on failure; stays until dismissed or replaced. */
  error?: string | null;
  onErrorClose?: () => void;
  /** Milliseconds before a success message hides itself. */
  autoHideDuration?: number;
}

const regionSx = {
  position: 'fixed',
  left: '50%',
  transform: 'translateX(-50%)',
  bottom: 24,
  zIndex: (theme: { zIndex: { snackbar: number } }) => theme.zIndex.snackbar,
  display: 'flex',
  flexDirection: 'column',
  gap: 1,
  maxWidth: 'calc(100vw - 32px)',
} as const;

export default function ActionFeedback({
  success,
  onSuccessClose,
  error,
  onErrorClose,
  autoHideDuration = 5000,
}: ActionFeedbackProps) {
  const { t } = useI18n();

  React.useEffect(() => {
    if (!success) return;
    const timer = window.setTimeout(() => onSuccessClose?.(), autoHideDuration);
    return () => window.clearTimeout(timer);
  }, [success, autoHideDuration, onSuccessClose]);

  return (
    <Box sx={regionSx}>
      {/* Both regions exist from first paint: assistive tech subscribes before
          the first message, and swapping text inside a stable live region is
          what actually gets announced. */}
      <Box role="status" aria-live="polite" data-testid="action-feedback-success">
        {success && (
          <Alert severity="success" variant="filled" onClose={onSuccessClose}>{t(success)}</Alert>
        )}
      </Box>
      <Box role="alert" aria-live="assertive" data-testid="action-feedback-error">
        {error && (
          <Alert severity="error" variant="filled" onClose={onErrorClose}>{t(error)}</Alert>
        )}
      </Box>
    </Box>
  );
}
