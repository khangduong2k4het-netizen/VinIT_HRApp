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
      {items.map(item => (
        <Card key={item.item_id} variant="outlined" sx={{ borderColor: '#E4EAF2', '&:hover': { borderColor: '#B9CBE2', boxShadow: '0 3px 12px rgba(10,43,87,.06)' } }}>
          <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', py: 2 }}>
            <Box sx={{ minWidth: 240, flex: 1 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
                <Chip size="small" label={t(PRIORITY_LABELS[item.priority])} color={item.priority === 'HIGH' ? 'error' : item.priority === 'MEDIUM' ? 'warning' : 'default'} variant="outlined" />
                <Typography variant="caption" color="text.secondary" fontFamily="monospace">{item.position_code || ''}</Typography>
              </Box>
              <Typography variant="body1" fontWeight={700} color="#0A2B57">{t(TYPE_LABELS[item.type])}</Typography>
              <Typography variant="body2" color="text.secondary">{item.position_title || t("Vị trí tuyển dụng")}</Typography>
            </Box>
            <Typography variant="h3" sx={{ fontSize: 24, color: item.priority === 'HIGH' ? '#B42318' : '#0A2B57', minWidth: 48, textAlign: 'center' }}>{item.count}</Typography>
            <Button component={Link} href={hrefFor(item)} variant={item.priority === 'HIGH' ? 'contained' : 'outlined'} color={item.priority === 'HIGH' ? 'secondary' : 'primary'} endIcon={<ArrowForwardIcon />}>
              {t(TYPE_ACTIONS[item.type])}
            </Button>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}
