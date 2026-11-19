'use client';

import * as React from 'react';
import { Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import Link from 'next/link';
import { useI18n } from '@/i18n/I18nProvider';
import HrSettings from '../HrSettings';

/**
 * Standalone route for the HR thresholds.
 *
 * The settings are also a tab inside /admin, which is the AI configuration
 * screen. This page exists so HR can reach the two numbers without loading (and
 * scrolling past) AI provider configuration, and so the screen can be reviewed
 * on its own.
 */
export default function HrSettingsPage() {
  const { t } = useI18n();
  return (
    <Box>
      <Button component={Link} href="/admin" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>
        {t('Quay lại quản trị')}
      </Button>
      <Typography variant="h1" sx={{ fontSize: 26, color: '#0A2B57' }}>{t('Cài đặt HR')}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 3 }}>
        {t('Ngưỡng thời gian dùng chung cho Dashboard và danh sách ứng viên.')}
      </Typography>
      <HrSettings />
    </Box>
  );
}
