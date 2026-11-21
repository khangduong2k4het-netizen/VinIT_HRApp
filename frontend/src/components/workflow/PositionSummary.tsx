'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

/**
 * Dải số liệu của vị trí.
 *
 * Trước đây là 6 thẻ riêng trong một grid: chiếm gần một màn hình, đẩy phần
 * việc thật (tiêu chí, hồ sơ) xuống dưới, và trông như một dashboard con nằm
 * trong trang. Nay gộp thành một dải chữ ngang, HR đọc được cùng lúc 6 con số
 * mà không phải cuộn; mỗi số vẫn bấm được để mở đúng hàng đợi.
 */
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
  const positionId = workspace.position.position_id;

  return (
    <Box
      aria-label={t("Tóm tắt hồ sơ của vị trí")}
      sx={{ display: 'flex', alignItems: 'center', columnGap: 0.5, rowGap: 1, flexWrap: 'wrap' }}
    >
      {cards.map(card => {
        const body = (
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75, px: 1, py: 0.5, borderRadius: 1 }}>
            <Typography component="span" sx={{ fontSize: 22, fontWeight: 700, lineHeight: 1.1, color: card.color }}>{card.value}</Typography>
            <Typography component="span" variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>{card.label}</Typography>
          </Box>
        );
        if (!isHR || card.path === null) return <Box key={card.label}>{body}</Box>;
        const href = card.path.startsWith('?tab=')
          ? `/positions/${positionId}${card.path}`
          : `/positions/${positionId}/applicants${card.path}`;
        return (
          <Box
            key={card.label}
            component={Link}
            href={href}
            aria-label={`${card.label}: ${card.value} — ${t('Mở danh sách liên quan')}`}
            sx={{ textDecoration: 'none', color: 'inherit', borderRadius: 1, '&:hover': { backgroundColor: '#F5F8FC' } }}
          >
            {body}
          </Box>
        );
      })}
      <Typography variant="caption" color="text.disabled" sx={{ px: 1 }}>
        {t('Các hàng đợi chỉ hiển thị hồ sơ trong giai đoạn sàng lọc.')}
      </Typography>
    </Box>
  );
}
