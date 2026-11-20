'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useI18n } from '@/i18n/I18nProvider';
import type { WorkQueueItem } from '@/types';
import EmptyState from '@/components/common/EmptyState';
import { deadlineNote, workQueueTypeAction, workQueueTypeLabel } from '@/lib/workQueueLabels';
import { workQueueListHref, workQueueNextHref } from '@/lib/workQueueEntry';
import { WORK_CLUSTERS, WORK_CLUSTER_LABELS, workQueueItemCluster } from '@/lib/workVocabulary';

const PRIORITY_LABELS: Record<WorkQueueItem['priority'], string> = {
  HIGH: 'Ưu tiên cao',
  MEDIUM: 'Ưu tiên trung bình',
  LOW: 'Ưu tiên thấp',
};

/**
 * Hàng đợi việc làm được nhóm theo ba cụm nghiệp vụ dùng chung với trang xếp
 * hạng (lib/workVocabulary.ts): việc còn phải làm, việc đang chờ quyết, và
 * việc đã quyết xong.
 */
export default function WorkQueueList({ items, doneCount = 0 }: { items: WorkQueueItem[]; doneCount?: number }) {
  const { t } = useI18n();

  if (items.length === 0 && doneCount === 0) {
    return <EmptyState title={t("Không có việc đang chờ")} description={t("Khi có tiêu chí, file CV hoặc hồ sơ cần xử lý, việc sẽ xuất hiện tại đây.")} />;
  }

  const renderItem = (item: WorkQueueItem) => {
    const note = deadlineNote(item, t);
    // Việc gắn với hồ sơ mở thẳng hồ sơ chờ lâu nhất; danh sách đã lọc vẫn còn
    // đó làm lựa chọn thứ hai để HR tự chọn hồ sơ khác.
    const nextHref = workQueueNextHref(item);
    const listHref = workQueueListHref(item);
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
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            {nextHref && (
              <Button
                component={Link}
                href={nextHref}
                variant={item.priority === 'HIGH' ? 'contained' : 'outlined'}
                color={item.priority === 'HIGH' ? 'secondary' : 'primary'}
                endIcon={<ArrowForwardIcon />}
                data-testid="work-next"
              >
                {t('Duyệt hồ sơ tiếp theo')}
              </Button>
            )}
            <Button
              component={Link}
              href={listHref}
              variant={nextHref ? 'text' : (item.priority === 'HIGH' ? 'contained' : 'outlined')}
              color={nextHref ? 'inherit' : (item.priority === 'HIGH' ? 'secondary' : 'primary')}
              data-testid="work-list"
            >
              {t(workQueueTypeAction(item))}
            </Button>
          </Box>
        </CardContent>
      </Card>
    );
  };

  return (
    <Stack spacing={2.5} aria-label={t("Danh sách việc cần làm")}>
      {WORK_CLUSTERS.map(cluster => {
        const rows = items.filter(item => workQueueItemCluster(item.type) === cluster);
        return (
          <Box key={cluster} data-testid={`work-cluster-${cluster}`}>
            <Typography variant="h3" sx={{ fontSize: 15, color: '#0A2B57', mb: 1 }}>
              {t(WORK_CLUSTER_LABELS[cluster])}
              <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1, fontWeight: 400 }}>
                {cluster === 'DONE' ? t("{0} hồ sơ đã xác minh xong", doneCount) : t("{0} việc", rows.length)}
              </Typography>
            </Typography>
            {cluster === 'DONE' ? (
              doneCount > 0 ? (
                <Typography variant="body2" color="text.secondary" data-testid="verification-complete-summary">
                  {t("Đã xác minh xong {0} hồ sơ — số trên chỉ tính việc còn lại", doneCount)}
                </Typography>
              ) : (
                <Typography variant="body2" color="text.secondary">{t("Chưa có hồ sơ nào được xác minh xong.")}</Typography>
              )
            ) : rows.length === 0 ? (
              <Typography variant="body2" color="text.secondary">{t("Không có việc nào trong nhóm này.")}</Typography>
            ) : (
              <Stack spacing={1.5}>{rows.map(renderItem)}</Stack>
            )}
          </Box>
        );
      })}
    </Stack>
  );
}
