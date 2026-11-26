'use client';

import * as React from 'react';
import { Box, Tooltip, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

const STEP_LABELS: Record<string, string> = {
  JD: 'JD',
  CRITERIA: 'Tiêu chí',
  CV_INTAKE: 'Tiếp nhận CV',
  HR_REVIEW: 'Đánh giá & HR rà soát',
  SHORTLIST: 'Shortlist / HM',
};

const STATUS_LABELS: Record<string, string> = {
  COMPLETED: 'Đã hoàn thành',
  CURRENT: 'Đang thực hiện',
  NOT_STARTED: 'Chưa bắt đầu',
  BLOCKED: 'Đang bị chặn',
};

function StepIcon({ status }: { status: string }) {
  if (status === 'COMPLETED') return <CheckCircleIcon sx={{ color: '#067647', fontSize: 16 }} aria-hidden />;
  if (status === 'BLOCKED') return <ErrorOutlineIcon sx={{ color: '#B42318', fontSize: 16 }} aria-hidden />;
  if (status === 'CURRENT') return <RadioButtonUncheckedIcon sx={{ color: '#C72127', fontSize: 16 }} aria-hidden />;
  return <RadioButtonUncheckedIcon sx={{ color: '#98A2B3', fontSize: 16 }} aria-hidden />;
}

/**
 * Tiến trình 5 bước dạng dải chip.
 *
 * Stepper dạng khối trước đây chiếm một thẻ riêng, lặp lại nhãn "Bước hiện tại"
 * và đẩy nội dung chính xuống thấp. Dải chip giữ nguyên thông tin (bước hiện
 * tại, bước bị chặn) nhưng chỉ cao một dòng và nằm chung thẻ tổng quan.
 */
export default function WorkflowStepper({ workspace }: { workspace: PositionWorkspace }) {
  const { t } = useI18n();

  return (
    <Box
      aria-label={t("Tiến trình tuyển dụng của vị trí")}
      sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}
    >
      {workspace.workflow.steps.map((step, index) => {
        const current = step.code === workspace.workflow.current_step;
        return (
          <React.Fragment key={step.code}>
            {index > 0 && <Typography component="span" color="text.disabled" sx={{ px: 0.25 }} aria-hidden>›</Typography>}
            <Tooltip title={t(STATUS_LABELS[step.status])}>
              <Box
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.25, borderRadius: 99,
                  backgroundColor: current ? '#FDF2F2' : 'transparent',
                  border: '1px solid', borderColor: current ? '#F3C2C6' : 'transparent',
                }}
              >
                <StepIcon status={step.status} />
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ fontWeight: current ? 700 : 500, color: step.status === 'BLOCKED' ? '#B42318' : current ? '#0A2B57' : '#667085', whiteSpace: 'nowrap' }}
                >
                  {t(STEP_LABELS[step.code])}
                </Typography>
              </Box>
            </Tooltip>
          </React.Fragment>
        );
      })}
    </Box>
  );
}
