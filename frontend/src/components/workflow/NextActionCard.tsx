'use client';

import * as React from 'react';
import Link from 'next/link';
import { Box, Button, Card, CardContent, Chip, Typography } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

const ACTION_LABELS: Record<string, string> = {
  CREATE_JD: 'Tạo JD',
  GENERATE_CRITERIA: 'Đề xuất tiêu chí',
  REVIEW_CRITERIA_HR: 'Rà soát tiêu chí',
  WAIT_HR_REVIEW: 'Xem trạng thái chờ HR',
  WAIT_HM_APPROVAL: 'Xem trạng thái chờ HM',
  WAIT_HR_SHORTLIST: 'Xem tiêu chí đã duyệt',
  APPROVE_CRITERIA_HM: 'Duyệt tiêu chí',
  REGENERATE_CRITERIA: 'Tạo phiên bản tiêu chí mới',
  VIEW_CRITERIA: 'Xem tiêu chí',
  UPLOAD_CV: 'Tải lên CV',
  VIEW_PROCESSING: 'Theo dõi xử lý',
  RUN_ASSESSMENT: 'Chạy matching',
  REVIEW_FILES: 'Kiểm tra file CV',
  REVIEW_DUPLICATES: 'Kiểm tra cảnh báo trùng',
  REVIEW_EVIDENCE: 'Tiếp tục xác minh bằng chứng',
  REVIEW_MISMATCH: 'Rà soát hồ sơ chưa đáp ứng',
  SHARE_SHORTLIST: 'Chia sẻ shortlist',
  VIEW_SHORTLIST: 'Mở Shortlist',
  VIEW_RANKING: 'Mở danh sách ứng viên',
  VIEW_ONLY_CLOSED: 'Xem thông tin vị trí',
};

const ACTION_DESCRIPTIONS: Record<string, string> = {
  CREATE_JD: 'Vị trí chưa có JD để bắt đầu quy trình.',
  GENERATE_CRITERIA: 'Tạo bộ tiêu chí nháp từ JD mới nhất trước khi tiếp nhận CV.',
  REVIEW_CRITERIA_HR: 'Bộ tiêu chí đang chờ HR rà soát và gửi HM.',
  WAIT_HR_REVIEW: 'Bộ tiêu chí đang chờ HR phụ trách rà soát.',
  WAIT_HM_APPROVAL: 'Bộ tiêu chí đang chờ Hiring Manager duyệt chuyên môn.',
  WAIT_HR_SHORTLIST: 'HR đang tiếp nhận và sàng lọc CV. Shortlist sẽ xuất hiện ở mục Shortlist khi HR chia sẻ với bạn.',
  APPROVE_CRITERIA_HM: 'Bộ tiêu chí đang chờ bạn duyệt chuyên môn.',
  REGENERATE_CRITERIA: 'Cần tạo hoặc điều chỉnh bộ tiêu chí cho JD hiện tại.',
  VIEW_CRITERIA: 'Xem lại bộ tiêu chí trước khi tiếp tục.',
  UPLOAD_CV: 'Bộ tiêu chí đã được duyệt. Hãy tiếp nhận CV để bắt đầu xử lý.',
  VIEW_PROCESSING: 'Hệ thống đang xử lý hồ sơ. Bạn có thể theo dõi tiến trình tại đây.',
  RUN_ASSESSMENT: 'Một số hồ sơ đã sẵn sàng nhưng chưa được matching.',
  REVIEW_FILES: 'Một số file CV cần HR kiểm tra trước khi đánh giá.',
  REVIEW_DUPLICATES: 'Một số hồ sơ có cảnh báo trùng cần được kiểm tra.',
  REVIEW_EVIDENCE: 'Một số hồ sơ cần HR xác minh bằng chứng trước khi quyết định.',
  REVIEW_MISMATCH: 'Một số hồ sơ có dấu hiệu chưa đáp ứng tiêu chí bắt buộc.',
  SHARE_SHORTLIST: 'Đã có hồ sơ shortlist. Hãy chọn và chia sẻ cho Hiring Manager.',
  VIEW_SHORTLIST: 'Theo dõi shortlist và phản hồi tại trang Shortlist.',
  VIEW_RANKING: 'Không còn việc ưu tiên. Mở danh sách để tiếp tục rà soát ứng viên.',
  VIEW_ONLY_CLOSED: 'Vị trí không còn mở để tiếp nhận hoặc xử lý thêm CV.',
};

interface NextActionCardProps {
  workspace: PositionWorkspace;
  onAction?: (action: PositionWorkspace['workflow']['next_action']) => void;
}

export default function NextActionCard({ workspace, onAction }: NextActionCardProps) {
  const { t } = useI18n();
  const action = workspace.workflow.next_action;
  const label = ACTION_LABELS[action.code] || 'Tiếp tục';
  const description = ACTION_DESCRIPTIONS[action.code] || 'Mở bước tiếp theo của vị trí.';
  const href = `${action.target.pathname}${action.target.search ? `?${action.target.search}` : ''}`;

  return (
    <Card sx={{ mb: 3, border: '1px solid #F3C2C6', borderLeft: '5px solid #C72127', backgroundColor: '#FFFBFB' }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ minWidth: 260, flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', mb: 0.75 }}>
            <Typography variant="overline" color="secondary.main">{t("Hành động tiếp theo")}</Typography>
            {action.blocked_reason_code && <Chip size="small" label={t("Đang chờ")} color="warning" variant="outlined" />}
          </Box>
          <Typography variant="h3" sx={{ fontSize: 18, color: '#0A2B57' }}>{t(label)}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{t(description)}</Typography>
        </Box>
        {onAction ? (
          <Button variant="contained" color="secondary" endIcon={<ArrowForwardIcon />} onClick={() => onAction(action)}>{t(label)}</Button>
        ) : (
          <Button component={Link} href={href} variant="contained" color="secondary" endIcon={<ArrowForwardIcon />}>{t(label)}</Button>
        )}
      </CardContent>
    </Card>
  );
}
