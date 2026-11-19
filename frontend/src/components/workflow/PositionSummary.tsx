'use client';

import * as React from 'react';
import { Box, Card, CardContent, Grid, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

export default function PositionSummary({ workspace }: { workspace: PositionWorkspace }) {
  const { t } = useI18n();
  const counts = workspace.counts;
  const cards = [
    { label: t('Tổng hồ sơ'), value: counts.total, color: '#0A2B57', dot: '#0A2B57' },
    { label: t('Đã matching'), value: counts.assessed, color: '#067647', dot: '#12B76A' },
    { label: t('Đang xử lý'), value: counts.processing, color: counts.processing ? '#B54708' : '#64748B', dot: counts.processing ? '#F79009' : '#CBD5E1' },
    { label: t('Cần kiểm tra file'), value: counts.file_review, color: counts.file_review ? '#B42318' : '#64748B', dot: counts.file_review ? '#F04438' : '#CBD5E1' },
    { label: t('Cần xác minh'), value: counts.needs_verification, color: counts.needs_verification ? '#B54708' : '#64748B', dot: counts.needs_verification ? '#F79009' : '#CBD5E1' },
    { label: t('Đã shortlist'), value: counts.shortlisted, color: '#067647', dot: '#12B76A' },
  ];

  return (
    <Grid container spacing={1.75} sx={{ mb: 2.5 }} aria-label={t('Tóm tắt hồ sơ của vị trí')}>
      {cards.map(card => (
        <Grid item xs={6} sm={4} md={2} key={card.label}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ py: 1.75, px: 2, '&:last-child': { pb: 1.75 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
                <Box component="span" aria-hidden sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: card.dot, flexShrink: 0 }} />
                <Typography variant="caption" noWrap sx={{ color: '#64748B', fontWeight: 500 }}>{card.label}</Typography>
              </Box>
              <Typography className="tabular-nums" sx={{ fontSize: 26, fontWeight: 700, color: card.color, lineHeight: 1.2 }}>
                {card.value}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
}
