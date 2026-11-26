'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, Link, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    try {
      setLoading(true);
      const response = await authApi.forgotPassword(email.trim());
      setMessage(response.data.message);
      // Only present when the server runs in development without an email channel.
      setDevLink(response.data.dev_reset_link || null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể gửi yêu cầu. Vui lòng thử lại."));
    } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 440 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Quên mật khẩu")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t("Nhập email tài khoản. Nếu tài khoản đang hoạt động, bạn sẽ nhận liên kết đặt lại mật khẩu (hiệu lực 30 phút, dùng một lần).")}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {message ? <>
        <Alert severity="success" sx={{ mb: 2 }}>{t(message)}</Alert>
        {devLink && <Alert severity="warning" sx={{ mb: 2, overflowWrap: 'anywhere' }}>
          {t("Chế độ phát triển (chưa cấu hình email):")} <Link href={devLink}>{t("Mở liên kết đặt lại mật khẩu")}</Link>
        </Alert>}
      </> : <Box component="form" onSubmit={submit}>
        <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" autoComplete="username" />
        <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
          {loading ? <CircularProgress size={22} color="inherit" /> : t("Gửi liên kết đặt lại")}
        </Button>
      </Box>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
