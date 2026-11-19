'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useI18n } from '@/i18n/I18nProvider';
import type { WorkQueueItem } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const TYPE_LABELS: Record<WorkQueueItem['type'], string> = {
  POSITION_SETUP: 'Thiết lập vị trí',
  CRITERIA_PENDING_HR: 'Tiêu chí chờ HR rà soát',
  CRITERIA_PENDING_HM: 'Tiêu chí chờ HM duyệt',
  FILE_REVIEW: 'File CV cần HR kiểm tra',
  PROCESSING: 'Hồ sơ đang xử lý',
  NEEDS_VERIFICATION: 'Hồ sơ cần xác minh bằng chứng',
  DUPLICATE_PENDING: 'Cảnh báo trùng cần kiểm tra',
  POSSIBLE_MISMATCH: 'Hồ sơ có dấu hiệu chưa đáp ứng',
  NOT_ASSESSED: 'Hồ sơ chưa matching',
  SHARE_WITHOUT_FEEDBACK: 'Shortlist chưa có phản hồi',
};

const TYPE_ACTIONS: Record<WorkQueueItem['type'], string> = {
  POSITION_SETUP: 'Tiếp tục thiết lập',
  CRITERIA_PENDING_HR: 'Rà soát tiêu chí',
  CRITERIA_PENDING_HM: 'Mở phê duyệt tiêu chí',
  FILE_REVIEW: 'Kiểm tra file',
  PROCESSING: 'Theo dõi xử lý',
  NEEDS_VERIFICATION: 'Xác minh hồ sơ',
  DUPLICATE_PENDING: 'Kiểm tra cảnh báo',
  POSSIBLE_MISMATCH: 'Mở hàng đợi rà soát',
  NOT_ASSESSED: 'Mở danh sách hồ sơ',
  SHARE_WITHOUT_FEEDBACK: 'Mở Shortlist',
};

const PRIORITY_LABELS: Record<WorkQueueItem['priority'], string> = {
  HIGH: 'Ưu tiên cao',
  MEDIUM: 'Ưu tiên trung bình',
  LOW: 'Ưu tiên thấp',
};

const PRIORITY_STYLES: Record<WorkQueueItem['priority'], { bg: string; color: string; border: string; accent: string }> = {
  HIGH: { bg: '#FEF2F2', color: '#B42318', border: '#FECACA', accent: '#C72127' },
  MEDIUM: { bg: '#FFFAEB', color: '#B54708', border: '#FEDF89', accent: '#D97706' },
  LOW: { bg: '#F1F5F9', color: '#475569', border: '#E2E8F0', accent: '#94A3B8' },
};

function hrefFor(item: WorkQueueItem) {
  return `${item.target.pathname}${item.target.search ? `?${item.target.search}` : ''}`;
}

export default function WorkQueueList({ items }: { items: WorkQueueItem[] }) {
  const { t } = useI18n();

  if (items.length === 0) {
    return (
      <EmptyState
        title={t('Không có việc đang chờ')}
        description={t('Khi có tiêu chí, file CV hoặc hồ sơ cần xử lý, việc sẽ xuất hiện tại đây.')}
      />
    );
  }

  return (
    <Stack spacing={1.25} aria-label={t('Danh sách việc cần làm')}>
      {items.map(item => {
        const p = PRIORITY_STYLES[item.priority];
        return (
          <Card
            key={item.item_id}
            sx={{
              borderLeft: `3.5px solid ${p.accent}`,
              '&:hover': {
                borderColor: '#CBD5E1',
                borderLeftColor: p.accent,
                boxShadow: '0 6px 16px rgba(10, 43, 87, 0.06)',
              },
            }}
          >
            <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', py: 1.75, px: 2.25, '&:last-child': { pb: 1.75 } }}>
              <Box sx={{ minWidth: 240, flex: 1 }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
                  <Chip
                    size="small"
                    label={t(PRIORITY_LABELS[item.priority])}
                    sx={{
                      bgcolor: p.bg,
                      color: p.color,
                      border: `1px solid ${p.border}`,
                      fontWeight: 600,
                      fontSize: 11,
                      height: 22,
                    }}
                  />
                  {item.position_code && (
                    <Typography variant="caption" className="mono-code" sx={{ color: '#64748B', fontSize: 11.5 }}>
                      {item.position_code}
                    </Typography>
                  )}
                </Box>
                <Typography variant="body1" fontWeight={600} color="#0F172A">
                  {t(TYPE_LABELS[item.type])}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ fontSize: 13 }}>
                  {item.position_title || t('Vị trí tuyển dụng')}
                </Typography>
              </Box>
              <Box
                sx={{
                  minWidth: 48,
                  px: 1.5,
                  py: 0.5,
                  borderRadius: '8px',
                  bgcolor: item.priority === 'HIGH' ? '#FEF2F2' : '#EEF4FC',
                  textAlign: 'center',
                }}
              >
                <Typography
                  className="tabular-nums"
                  sx={{ fontSize: 20, fontWeight: 700, color: item.priority === 'HIGH' ? '#B42318' : '#0A2B57', lineHeight: 1.2 }}
                >
                  {item.count}
                </Typography>
              </Box>
              <Button
                component={Link}
                href={hrefFor(item)}
                size="small"
                variant={item.priority === 'HIGH' ? 'contained' : 'outlined'}
                color={item.priority === 'HIGH' ? 'secondary' : 'primary'}
                endIcon={<ArrowForwardIcon fontSize="small" />}
              >
                {t(TYPE_ACTIONS[item.type])}
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </Stack>
  );
}
