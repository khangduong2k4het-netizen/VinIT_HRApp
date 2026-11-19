'use client';

import * as React from 'react';
import { Box, Chip } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { ApplicantQueue } from '@/lib/applicantReview';

const QUEUE_LABELS: Record<ApplicantQueue, string> = {
  ALL: 'Tất cả',
  FILE_REVIEW: 'Cần kiểm tra file',
  NEEDS_VERIFICATION: 'Cần xác minh',
  DUPLICATE: 'Cảnh báo trùng',
  POSSIBLE_MISMATCH: 'Có dấu hiệu chưa đáp ứng',
  NOT_ASSESSED: 'Chưa matching',
  MEETS_MANDATORY: 'Đáp ứng bắt buộc',
};

interface QueueFilterChipsProps {
  value: ApplicantQueue;
  counts: Record<ApplicantQueue, number>;
  onChange: (queue: ApplicantQueue) => void;
}

export default function QueueFilterChips({ value, counts, onChange }: QueueFilterChipsProps) {
  const { t } = useI18n();
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }} role="group" aria-label={t("Hàng đợi rà soát ứng viên")}>
      {(Object.keys(QUEUE_LABELS) as ApplicantQueue[]).map(queue => {
        const selected = value === queue;
        return (
          <Chip
            key={queue}
            label={`${t(QUEUE_LABELS[queue])} (${counts[queue]})`}
            onClick={() => onChange(queue)}
            aria-pressed={selected}
            color={selected ? 'primary' : 'default'}
            variant={selected ? 'filled' : 'outlined'}
            sx={{ fontWeight: selected ? 700 : 500 }}
          />
        );
      })}
    </Box>
  );
}
