'use client';

import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';

/** Bước hiện tại của việc tạo vị trí + sinh tiêu chí tự động. */
export type CreateProgressStep = 'creating' | 'generating' | 'done';

/**
 * Hộp thoại chặn màn hình khi vừa tạo vị trí và hệ thống tự sinh tiêu chí.
 *
 * Vì sao chặn thay vì chỉ hiện spinner trong nút: hai lời gọi này có thể mất
 * vài chục giây (LLM đọc JD rồi sinh tiêu chí). Nếu người dùng sửa form hoặc
 * bấm lại trong lúc đó, họ có thể tạo ra vị trí thứ hai. Hộp thoại nói rõ đang
 * ở bước nào và không cho thao tác cho tới khi xong.
 */
export default function CreatePositionProgressDialog({
  open, step, error, onRetryGenerate, onEnterPosition,
}: {
  open: boolean;
  step: CreateProgressStep;
  error: string;
  onRetryGenerate: () => void;
  onEnterPosition: () => void;
}) {
  const { t } = useI18n();
  const label = step === 'creating'
    ? t('Đang tạo vị trí tuyển dụng...')
    : step === 'generating'
      ? t('Đang tạo tiêu chí tự động cho vị trí tuyển dụng này...')
      : t('Đã tạo xong tiêu chí. Đang mở vị trí...');

  return <Dialog
    open={open}
    fullWidth
    maxWidth="sm"
    // Chặn cả Esc và click ra ngoài: đóng giữa chừng sẽ để lại vị trí đã tạo
    // nhưng người dùng không biết tiêu chí đã sinh xong hay chưa.
    disableEscapeKeyDown
    onClose={() => {}}
    aria-labelledby="create-position-progress-title"
  >
    <DialogTitle id="create-position-progress-title">{t('Tạo vị trí tuyển dụng')}</DialogTitle>
    <DialogContent>
      {!error && <Box sx={{ py: 1 }}>
        <Typography sx={{ mb: 2 }} data-testid="create-progress-label">{label}</Typography>
        <LinearProgress
          // Không có tiến trình thật để đo: LLM không báo phần trăm. Dùng thanh
          // chạy vô định thay vì một con số giả.
          variant={step === 'done' ? 'determinate' : 'indeterminate'}
          value={step === 'done' ? 100 : undefined}
          aria-label={label}
        />
        {step === 'generating' && <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          {t('Bước này có thể mất vài chục giây. Vui lòng không đóng trang.')}
        </Typography>}
      </Box>}

      {error && <Alert severity="warning" sx={{ mt: 1 }} data-testid="create-progress-error">
        <Typography sx={{ fontWeight: 600, mb: 0.5 }}>
          {t('Đã tạo vị trí nhưng chưa tạo được tiêu chí.')}
        </Typography>
        <Typography variant="body2">{error}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          {t('Vị trí đã được lưu. Bạn có thể thử tạo tiêu chí lại, hoặc mở vị trí và tạo sau.')}
        </Typography>
      </Alert>}
    </DialogContent>
    {error && <DialogActions>
      <Button onClick={onEnterPosition}>{t('Mở vị trí')}</Button>
      <Button variant="contained" onClick={onRetryGenerate}>{t('Thử tạo tiêu chí lại')}</Button>
    </DialogActions>}
  </Dialog>;
}
