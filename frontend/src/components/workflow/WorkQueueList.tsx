'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useI18n } from '@/i18n/I18nProvider';
import type { WorkQueueItem } from '@/types';
import EmptyState from '@/components/common/EmptyState';
import { deadlineNote, workQueueTypeAction, workQueueTypeLabel } from '@/lib/workQueueLabels';

const PRIORITY_LABELS: Record<WorkQueueItem['priority'], string> = {
  HIGH: 'Ưu tiên cao',
  MEDIUM: 'Ưu tiên trung bình',
  LOW: 'Ưu tiên thấp',
};

function hrefFor(item: WorkQueueItem) {
  return `${item.target.pathname}${item.target.search ? `?${item.target.search}` : ''}`;
}

export default function WorkQueueList({ items }: { items: WorkQueueItem[] }) {
  const { t } = useI18n();

  if (items.length === 0) {
    return <EmptyState title={t("Không có việc đang chờ")} description={t("Khi có tiêu chí, file CV hoặc hồ sơ cần xử lý, việc sẽ xuất hiện tại đây.")} />;
  }

  return (
    <Stack spacing={1.5} aria-label={t("Danh sách việc cần làm")}>
      {items.map(item => {
        const note = deadlineNote(item, t);
        return (
        <Card key={item.item_id} variant="outlined" sx={{ borderColor: '#E4EAF2', '&:hover': { borderColor: '#B9CBE2', boxShadow: '0 3px 12px rgba(10,43,87,.06)' } }}>
          <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', py: 2 }}>
            <Box sx={{ minWidth: 240, flex: 1 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
                <Chip size="small" label={t(PRIORITY_LABELS[item.priority])} color={item.priority === 'HIGH' ? 'error' : item.priority === 'MEDIUM' ? 'warning' : 'default'} variant="outlined" />
                <Typography variant="caption" color="text.secondary" fontFamily="monospace">{item.position_code || ''}</Typography>
              </Box>
              <Typography variant="body1" fontWeight={700} color="#0A2B57">{t(workQueueTypeLabel(item))}</Typography>
              <Typography variant="body2" color="text.secondary">{item.position_title || t("Vị trí tuyển dụng")}</Typography>
              {note && (
                <Typography variant="body2" fontWeight={item.days_left! < 0 ? 700 : 400} color={item.days_left! < 0 ? '#B42318' : 'text.secondary'}>
                  {note}
                </Typography>
              )}
            </Box>
            <Typography variant="h3" sx={{ fontSize: 24, color: item.priority === 'HIGH' ? '#B42318' : '#0A2B57', minWidth: 48, textAlign: 'center' }}>{item.count}</Typography>
            <Button component={Link} href={hrefFor(item)} variant={item.priority === 'HIGH' ? 'contained' : 'outlined'} color={item.priority === 'HIGH' ? 'secondary' : 'primary'} endIcon={<ArrowForwardIcon />}>
              {t(workQueueTypeAction(item))}
            </Button>
          </CardContent>
        </Card>
        );
      })}
    </Stack>
  );
}
