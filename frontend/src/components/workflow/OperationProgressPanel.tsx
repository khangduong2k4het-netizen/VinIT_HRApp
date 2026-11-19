'use client';

import * as React from 'react';
import { Alert, Box, Card, CardContent, CircularProgress, LinearProgress, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import type { OperationStatus } from '@/types';

interface OperationProgressPanelProps {
  operation: OperationStatus;
  processingCount?: number;
}

export default function OperationProgressPanel({ operation, processingCount }: OperationProgressPanelProps) {
  const { t, locale } = useI18n();
  const status = operation.status || '';
  const isAssessment = operation.stage === 'ASSESSMENT' || operation.capability === 'ASSESSMENT' || operation.capability === 'RANKING';
  const progress = operation.progress;

  if (status === 'FAILED') {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {t("Xử lý thất bại:")} {operation.error_message ? localizeServerMessage(operation.error_message, locale) : t("Lỗi không xác định")}
      </Alert>
    );
  }

  if (status === 'COMPLETED') {
    return (
      <Alert severity={progress?.failed ? 'warning' : 'success'} sx={{ mb: 3 }}>
        {progress?.total && !progress.processed ? t("Không có tệp nào được xử lý thành công.") : t("Đã hoàn tất xử lý và cập nhật kết quả.")}
        {progress?.failed ? t(" Có {0} tệp cần kiểm tra.", progress.failed) : ''}
        {(progress?.invalid_files || []).map((file, index) => (
          <Typography key={`${file.original_filename}-${index}`} variant="caption" display="block">
            {file.original_filename}: {t("Tệp không hợp lệ hoặc vượt giới hạn.")}
          </Typography>
        ))}
      </Alert>
    );
  }

  return (
    <Card sx={{ mb: 3, borderLeft: '4px solid #2599DC', borderColor: '#E4EAF2' }} aria-live="polite">
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <CircularProgress size={20} aria-label={t("Đang xử lý")} />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" fontWeight={600} color="#0A2B57">
              {isAssessment ? t("Đang đánh giá và tạo xếp hạng…") : t("Đang xử lý CV…")}
            </Typography>
            {progress ? (
              <>
                <LinearProgress variant="determinate" value={progress.percent_complete || 0} sx={{ mt: 1.25, height: 7, borderRadius: 4 }} />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: 'block' }}>
                  {t("Đã xử lý")} {progress.processed}/{progress.total} {t("tệp")}
                  {progress.failed > 0 ? t(" ({0} lỗi)", progress.failed) : ''}
                </Typography>
              </>
            ) : processingCount ? (
              <Typography variant="caption" color="text.secondary">{t("Có {0} hồ sơ đang được xử lý.", processingCount)}</Typography>
            ) : (
              <Typography variant="caption" color="text.secondary">{t("Hệ thống đang cập nhật tiến trình.")}</Typography>
            )}
            {(progress?.invalid_files || []).length > 0 && (
              <Box sx={{ mt: 1 }}>
                {progress!.invalid_files!.map((file, index) => (
                  <Typography key={`${file.original_filename}-${index}`} variant="caption" display="block" color="error.main">
                    {file.original_filename}: {t("Tệp không hợp lệ hoặc vượt giới hạn.")}
                  </Typography>
                ))}
              </Box>
            )}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
