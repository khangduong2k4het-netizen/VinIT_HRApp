'use client';

import * as React from 'react';
import { Box, Card, CardContent, Chip, Step, StepLabel, Stepper, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RadioButtonCheckedIcon from '@mui/icons-material/RadioButtonChecked';
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
  if (status === 'COMPLETED') return <CheckCircleIcon sx={{ color: '#067647', fontSize: 22 }} aria-hidden />;
  if (status === 'BLOCKED') return <ErrorOutlineIcon sx={{ color: '#B42318', fontSize: 22 }} aria-hidden />;
  if (status === 'CURRENT') return <RadioButtonCheckedIcon sx={{ color: '#C72127', fontSize: 22 }} aria-hidden />;
  return <RadioButtonUncheckedIcon sx={{ color: '#CBD5E1', fontSize: 22 }} aria-hidden />;
}

export default function WorkflowStepper({ workspace }: { workspace: PositionWorkspace }) {
  const { t } = useI18n();
  const activeIndex = Math.max(0, workspace.workflow.steps.findIndex(step => step.code === workspace.workflow.current_step));

  return (
    <Card sx={{ mb: 2.5 }} aria-label={t('Tiến trình tuyển dụng của vị trí')}>
      <CardContent sx={{ py: 2.25 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <Typography variant="h4" sx={{ color: '#0F172A' }}>{t('Tiến trình vị trí')}</Typography>
          <Chip
            size="small"
            label={`${t('Bước hiện tại:')} ${t(STEP_LABELS[workspace.workflow.current_step])}`}
            sx={{ bgcolor: '#EEF4FC', color: '#0A2B57', border: '1px solid #C7DDF7', fontWeight: 600 }}
          />
        </Box>
        <Stepper
          activeStep={activeIndex}
          alternativeLabel
          sx={{
            '& .MuiStepLabel-label': { fontSize: 12.5, fontWeight: 600, mt: 0.75 },
            '& .MuiStepConnector-line': { borderColor: '#E2E8F0' },
          }}
        >
          {workspace.workflow.steps.map(step => (
            <Step key={step.code} completed={step.status === 'COMPLETED'} active={step.code === workspace.workflow.current_step}>
              <StepLabel StepIconComponent={() => <StepIcon status={step.status} />} error={step.status === 'BLOCKED'}>
                {t(STEP_LABELS[step.code])}
                <Typography component="span" variant="caption" display="block" color="text.secondary" sx={{ fontWeight: 400 }}>
                  {t(STATUS_LABELS[step.status])}
                </Typography>
              </StepLabel>
            </Step>
          ))}
        </Stepper>
      </CardContent>
    </Card>
  );
}
