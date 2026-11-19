'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Card, CardActionArea, CardContent, Grid, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

export default function PositionSummary({ workspace, isHR }: { workspace: PositionWorkspace; isHR: boolean }) {
  const { t } = useI18n();
  const counts = workspace.counts;
  const cards = [
    { label: t("Tổng hồ sơ"), value: counts.total, color: '#0A2B57', path: '?tab=applications' },
    { label: t("Đã đánh giá"), value: counts.assessed, color: '#067647', path: null },
    { label: t("Đang xử lý"), value: counts.processing, color: counts.processing ? '#B54708' : '#667085', path: '?tab=applications' },
    { label: t("Cần kiểm tra file"), value: counts.file_review, color: counts.file_review ? '#B42318' : '#667085', path: '?queue=FILE_REVIEW' },
    { label: t("Cần xác minh"), value: counts.needs_verification, color: counts.needs_verification ? '#B54708' : '#667085', path: '?queue=NEEDS_VERIFICATION' },
    { label: t("Đã shortlist"), value: counts.shortlisted, color: '#067647', path: '?queue=SHORTLIST' },
  ];

  return (
    <Box sx={{ mb: 3 }}><Grid container spacing={2} sx={{ mb: 3 }} aria-label={t("Tóm tắt hồ sơ của vị trí")}>
      {cards.map(card => (
        <Grid item xs={6} md={2} key={card.label}>
          <Card variant="outlined" sx={{ height: '100%', borderColor: '#E4EAF2' }}>
            {isHR && card.path !== null ? <CardActionArea component={Link} href={card.path.startsWith('?tab=') ? `/positions/${workspace.position.position_id}${card.path}` : `/positions/${workspace.position.position_id}/applicants${card.path}`} aria-label={`${card.label}: ${card.value} — ${t('Mở danh sách liên quan')}`}><CardContent sx={{ py: 2 }}>
              <Typography variant="caption" color="text.secondary">{card.label}</Typography>
              <Typography variant="h3" sx={{ fontSize: 26, fontWeight: 700, color: card.color, mt: 0.5 }}>{card.value}</Typography>
            </CardContent></CardActionArea> : <CardContent sx={{ py: 2 }}><Typography variant="caption" color="text.secondary">{card.label}</Typography><Typography variant="h3" sx={{ fontSize: 26, fontWeight: 700, color: card.color, mt: 0.5 }}>{card.value}</Typography></CardContent>}
          </Card>
        </Grid>
      ))}
    </Grid><Typography variant="caption" color="text.secondary">{t('Các hàng đợi chỉ hiển thị hồ sơ trong giai đoạn sàng lọc; số tổng hợp có thể bao gồm các trạng thái khác.')}</Typography></Box>
  );
}
