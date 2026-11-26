'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

function VerifyEmail() {
  const { t } = useI18n();
  const router = useRouter();
  const token = useSearchParams().get('token') || '';
  const [state, setState] = useState<'working' | 'done' | 'failed'>(token ? 'working' : 'failed');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    authApi.verifyEmail(token)
      .then(() => { if (active) setState('done'); })
      .catch((err: any) => { if (active) { setError(err.response?.data?.detail || null); setState('failed'); } });
    return () => { active = false; };
  }, [token]);

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 440 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 2 }}>{t("Xác minh email")}</Typography>
      {state === 'working' && <CircularProgress size={24} aria-label={t("Đang kiểm tra")} />}
      {state === 'done' && <Alert severity="success">{t("Đã xác minh email. Tài khoản đang chờ Admin duyệt; bạn có thể đăng nhập sau khi được duyệt.")}</Alert>}
      {state === 'failed' && <Alert severity="warning">{t(error || "Liên kết xác minh không hợp lệ hoặc đã hết hạn.")}</Alert>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}

export default function VerifyEmailPage() {
  return <Suspense fallback={null}><VerifyEmail /></Suspense>;
}
