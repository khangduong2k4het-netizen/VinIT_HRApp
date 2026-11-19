'use client';

import * as React from 'react';
import { Box, Button, Card, CardContent, CircularProgress, IconButton, Tooltip, Typography } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { useI18n } from '@/i18n/I18nProvider';

interface CVDocumentViewerProps {
  cvUrl: string | null;
  cvError: string | null;
  isPdf: boolean;
  canViewCv: boolean;
  selectedPage: number;
  onPageChange: (page: number) => void;
  /** The file is fetched on demand, never just because the profile opened. */
  requested?: boolean;
  loading?: boolean;
  onRequest?: () => void;
}

export default function CVDocumentViewer({ cvUrl, cvError, isPdf, canViewCv, selectedPage, onPageChange, requested = true, loading = false, onRequest }: CVDocumentViewerProps) {
  const { t } = useI18n();
  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57' }}>{t("CV gốc")}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title={t("Trang trước")}>
            <span>
              <IconButton aria-label={t("Trang trước")} size="small" disabled={!cvUrl || !isPdf || selectedPage <= 1} onClick={() => onPageChange(selectedPage - 1)}>
                <NavigateBeforeIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="body2">{t("Trang")} {selectedPage}</Typography>
          <Tooltip title={t("Trang sau")}>
            <span>
              <IconButton aria-label={t("Trang sau")} size="small" disabled={!cvUrl || !isPdf} onClick={() => onPageChange(selectedPage + 1)}>
                <NavigateNextIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      <Card sx={{ height: 'calc(100vh - 250px)', minHeight: 420, overflow: 'auto' }}>
        <CardContent sx={{ p: 0, height: '100%' }}>
          {cvUrl && isPdf ? (
            <Box sx={{ height: '100%', backgroundColor: '#525659', padding: 2 }}>
              <iframe id="cv-pdf-viewer" src={`${cvUrl}#page=${selectedPage}`} width="100%" height="100%" style={{ border: 'none', backgroundColor: 'white' }} title={t("CV gốc")} />
            </Box>
          ) : !canViewCv ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{t("Shortlist này không cho phép xem CV gốc.")}</Typography>
            </Box>
          ) : !requested ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5, height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{t("CV gốc chưa được tải. Bằng chứng AI bên trái đọc được mà không cần mở tệp.")}</Typography>
              <Button variant="outlined" startIcon={<VisibilityIcon />} onClick={onRequest} disabled={!onRequest}>{t("Xem CV gốc")}</Button>
              <Typography variant="caption">{t("Tệp được tải và ghi nhận truy cập khi bạn bấm, không tự tải khi mở hồ sơ.")}</Typography>
            </Box>
          ) : loading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 1.5, p: 3 }}>
              <CircularProgress size={20} /><Typography variant="body2" color="text.secondary">{t("Đang tải CV…")}</Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{cvError ? t(cvError) : (cvUrl && !isPdf ? t("Tệp DOCX cần được tải xuống để xem.") : t("Không thể tải CV. Vui lòng thử lại."))}</Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </>
  );
}
