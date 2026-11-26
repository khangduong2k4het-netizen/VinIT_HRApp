'use client';

import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

function ResetPasswordForm() {
  const { t } = useI18n();
  const router = useRouter();
  const token = useSearchParams().get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      await authApi.resetPassword(token, password);
      setPassword(''); setConfirm(''); setDone(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể đặt lại mật khẩu."));
    } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 440 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Đặt lại mật khẩu")}</Typography>
      {error && <Alert severity="error" sx={{ my: 2 }}>{t(error)}</Alert>}
      {done ? <Alert severity="success" sx={{ my: 2 }}>{t("Đã đặt lại mật khẩu. Hãy đăng nhập bằng mật khẩu mới.")}</Alert>
        : !token ? <Alert severity="warning" sx={{ my: 2 }}>{t("Liên kết đặt lại mật khẩu không hợp lệ. Hãy yêu cầu liên kết mới.")}</Alert>
        : <Box component="form" onSubmit={submit}>
          <TextField label={t("Mật khẩu mới")} type="password" value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
          <TextField label={t("Xác nhận mật khẩu")} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
          <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
            {loading ? <CircularProgress size={22} color="inherit" /> : t("Đặt lại mật khẩu")}
          </Button>
        </Box>}
      {!done && !token && <Button fullWidth sx={{ mt: 1 }} onClick={() => router.push('/forgot-password')}>{t("Yêu cầu liên kết mới")}</Button>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}

export default function ResetPasswordPage() {
  return <Suspense fallback={null}><ResetPasswordForm /></Suspense>;
}
