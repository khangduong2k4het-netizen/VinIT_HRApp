'use client';

import * as React from 'react';
import { Card, CardContent, Grid, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

export default function PositionSummary({ workspace }: { workspace: PositionWorkspace }) {
  const { t } = useI18n();
  const counts = workspace.counts;
  const cards = [
    { label: t("Tổng hồ sơ"), value: counts.total, color: '#0A2B57' },
    { label: t("Đã matching"), value: counts.assessed, color: '#067647' },
    { label: t("Đang xử lý"), value: counts.processing, color: counts.processing ? '#B54708' : '#667085' },
    { label: t("Cần kiểm tra file"), value: counts.file_review, color: counts.file_review ? '#B42318' : '#667085' },
    { label: t("Cần xác minh"), value: counts.needs_verification, color: counts.needs_verification ? '#B54708' : '#667085' },
    { label: t("Đã shortlist"), value: counts.shortlisted, color: '#067647' },
  ];

  return (
    <Grid container spacing={2} sx={{ mb: 3 }} aria-label={t("Tóm tắt hồ sơ của vị trí")}>
      {cards.map(card => (
        <Grid item xs={6} md={2} key={card.label}>
          <Card variant="outlined" sx={{ height: '100%', borderColor: '#E4EAF2' }}>
            <CardContent sx={{ py: 2 }}>
              <Typography variant="caption" color="text.secondary">{card.label}</Typography>
              <Typography variant="h3" sx={{ fontSize: 26, fontWeight: 700, color: card.color, mt: 0.5 }}>{card.value}</Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
}
