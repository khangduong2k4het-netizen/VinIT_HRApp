'use client';

import * as React from 'react';
import { Box, Card, CardContent, IconButton, Tooltip, Typography } from '@mui/material';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { useI18n } from '@/i18n/I18nProvider';

interface CVDocumentViewerProps {
  cvUrl: string | null;
  cvError: string | null;
  isPdf: boolean;
  // F2.06: JPG/PNG CVs are shown inline so HR can compare evidence with the original image.
  isImage?: boolean;
  canViewCv: boolean;
  selectedPage: number;
  onPageChange: (page: number) => void;
}

export default function CVDocumentViewer({ cvUrl, cvError, isPdf, isImage = false, canViewCv, selectedPage, onPageChange }: CVDocumentViewerProps) {
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
          ) : cvUrl && isImage ? (
            <Box sx={{ height: '100%', backgroundColor: '#525659', padding: 2, overflow: 'auto' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={cvUrl} alt={t("CV gốc")} style={{ maxWidth: '100%', backgroundColor: 'white', display: 'block', margin: '0 auto' }} />
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{!canViewCv ? t("Shortlist này không cho phép xem CV gốc.") : cvError ? t(cvError) : (cvUrl && !isPdf ? t("Tệp DOCX cần được tải xuống để xem.") : t("Không thể tải CV. Vui lòng thử lại."))}</Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </>
  );
}
