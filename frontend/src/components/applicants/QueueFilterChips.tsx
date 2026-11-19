'use client';

import * as React from 'react';
import { Box, Chip } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { APPLICANT_QUEUE_LABELS as QUEUE_LABELS, type ApplicantQueue } from '@/lib/applicantReview';

interface QueueFilterChipsProps {
  value: ApplicantQueue;
  counts: Record<ApplicantQueue, number>;
  onChange: (queue: ApplicantQueue) => void;
}

export default function QueueFilterChips({ value, counts, onChange }: QueueFilterChipsProps) {
  const { t } = useI18n();
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }} role="group" aria-label={t("Hàng đợi rà soát ứng viên")}
      title={t("Số trên mỗi nhóm tính trên toàn bộ hồ sơ của vị trí, không theo từ khóa đang tìm.")}>
      {(Object.keys(QUEUE_LABELS) as ApplicantQueue[]).map(queue => {
        const selected = value === queue;
        return (
          <Chip
            key={queue}
            label={`${t(QUEUE_LABELS[queue])} (${counts[queue]})`}
            aria-label={t("{0}: {1} hồ sơ trong toàn bộ vị trí", t(QUEUE_LABELS[queue]), counts[queue])}
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
