'use client';

import * as React from 'react';
import { Box, Card, CardContent, Step, StepLabel, Stepper, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { useI18n } from '@/i18n/I18nProvider';
import type { PositionWorkspace } from '@/types';

const STEP_LABELS: Record<string, string> = {
  JD: 'JD',
  CRITERIA: 'Tiêu chí',
  CV_INTAKE: 'Tiếp nhận CV',
  HR_REVIEW: 'Matching & HR rà soát',
  SHORTLIST: 'Shortlist / HM',
};

const STATUS_LABELS: Record<string, string> = {
  COMPLETED: 'Đã hoàn thành',
  CURRENT: 'Đang thực hiện',
  NOT_STARTED: 'Chưa bắt đầu',
  BLOCKED: 'Đang bị chặn',
};

function StepIcon({ status }: { status: string }) {
  if (status === 'COMPLETED') return <CheckCircleIcon sx={{ color: '#067647' }} aria-hidden />;
  if (status === 'BLOCKED') return <ErrorOutlineIcon sx={{ color: '#B42318' }} aria-hidden />;
  if (status === 'CURRENT') return <RadioButtonUncheckedIcon sx={{ color: '#C72127' }} aria-hidden />;
  return <RadioButtonUncheckedIcon sx={{ color: '#98A2B3' }} aria-hidden />;
}

export default function WorkflowStepper({ workspace }: { workspace: PositionWorkspace }) {
  const { t } = useI18n();
  const activeIndex = Math.max(0, workspace.workflow.steps.findIndex(step => step.code === workspace.workflow.current_step));

  return (
    <Card variant="outlined" sx={{ mb: 3, borderColor: '#E4EAF2' }} aria-label={t("Tiến trình tuyển dụng của vị trí")}>
      <CardContent sx={{ py: 2.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <Typography variant="h3" sx={{ fontSize: 16, color: '#0A2B57' }}>{t("Tiến trình vị trí")}</Typography>
          <Typography variant="caption" color="text.secondary">{t("Bước hiện tại:")} {t(STEP_LABELS[workspace.workflow.current_step])}</Typography>
        </Box>
        <Stepper activeStep={activeIndex} alternativeLabel sx={{ '& .MuiStepLabel-label': { fontSize: 12 } }}>
          {workspace.workflow.steps.map(step => (
            <Step key={step.code} completed={step.status === 'COMPLETED'} active={step.code === workspace.workflow.current_step}>
              <StepLabel StepIconComponent={() => <StepIcon status={step.status} />} error={step.status === 'BLOCKED'}>
                {t(STEP_LABELS[step.code])}
                <Typography component="span" variant="caption" display="block" color="text.secondary">{t(STATUS_LABELS[step.status])}</Typography>
              </StepLabel>
            </Step>
          ))}
        </Stepper>
      </CardContent>
    </Card>
  );
}
