'use client';

import * as React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { APPLICANT_QUEUE_LABELS as QUEUE_LABELS, type ApplicantQueue } from '@/lib/applicantReview';
import { WORK_CLUSTERS, WORK_CLUSTER_LABELS, applicantQueueCluster } from '@/lib/workVocabulary';

interface QueueFilterChipsProps {
  value: ApplicantQueue;
  counts: Record<ApplicantQueue, number>;
  onChange: (queue: ApplicantQueue) => void;
}

export default function QueueFilterChips({ value, counts, onChange }: QueueFilterChipsProps) {
  const { t } = useI18n();
  const chip = (queue: ApplicantQueue) => {
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
  };

  return (
    // Cụm được ghi ngay trước các chip của nó và chảy cùng dòng: nhóm rõ ràng
    // nhưng không thêm ba dòng tiêu đề đẩy bảng dữ liệu xuống dưới màn hình.
    <Box
      sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', mb: 2 }}
      role="group"
      aria-label={t("Hàng đợi rà soát ứng viên")}
      data-testid="queue-chip-counts"
      title={t("Số trên mỗi nhóm tính trên toàn bộ hồ sơ của vị trí, không theo từ khóa đang tìm.")}
    >
      {chip('ALL')}
      {WORK_CLUSTERS.map(cluster => {
        const queues = (Object.keys(QUEUE_LABELS) as ApplicantQueue[])
          .filter(queue => applicantQueueCluster(queue) === cluster);
        if (!queues.length) return null;
        return (
          <Box
            key={cluster}
            data-testid={`queue-cluster-${cluster}`}
            sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', alignItems: 'center' }}
          >
            <Typography
              component="span"
              variant="caption"
              color="text.secondary"
              sx={{ fontWeight: 700, pr: 0.5, borderLeft: '2px solid #D0D7E2', pl: 1 }}
            >
              {t(WORK_CLUSTER_LABELS[cluster])}
            </Typography>
            {queues.map(chip)}
          </Box>
        );
      })}
    </Box>
  );
}
