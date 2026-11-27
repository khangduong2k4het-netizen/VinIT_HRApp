'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

const REASON_MAX = 500;
const LINE_MAX = 100;

// Forgot password: the person writes why, an Admin checks and approves, then the reset link is emailed to the account.
export default function ForgotPasswordPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [reason, setReason] = useState('');
  const [fullName, setFullName] = useState('');
  const [unit, setUnit] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (fullName.trim().length < 2 || unit.trim().length < 2) { setError(t("Vui lòng nhập họ tên và đơn vị / phòng ban.")); return; }
    if (reason.trim().length < 5) { setError(t("Vui lòng ghi lý do (ít nhất 5 ký tự).")); return; }
    try {
      setLoading(true);
      const response = await authApi.requestPasswordReset(email.trim(), reason.trim(), fullName.trim(), unit.trim());
      setMessage(response.data.message);
    } catch (err: any) {
      setError(err.response?.status === 429 ? t("Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.") : t("Không thể gửi yêu cầu. Vui lòng thử lại."));
    } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 480 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Quên mật khẩu")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t("Nhập email công việc, họ tên, đơn vị và lý do. Admin sẽ kiểm tra; khi được duyệt, link đặt lại mật khẩu (hiệu lực 30 phút, dùng một lần) sẽ được gửi tới email đó.")}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {message ? <Alert severity="success" sx={{ mb: 2 }}>{t(message)}</Alert>
        : <Box component="form" onSubmit={submit}>
          <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" autoComplete="username" />
          <TextField label={t("Họ và tên")} value={fullName} onChange={e => setFullName(e.target.value)} fullWidth required margin="normal"
            inputProps={{ maxLength: LINE_MAX }} autoComplete="name" />
          <TextField label={t("Đơn vị / phòng ban")} value={unit} onChange={e => setUnit(e.target.value)} fullWidth required margin="normal"
            inputProps={{ maxLength: LINE_MAX }} helperText={t("Giúp Admin nhận ra bạn, kể cả khi bạn nhập chưa đúng email.")} />
          <TextField label={t("Lý do")} value={reason} onChange={e => setReason(e.target.value)} fullWidth required multiline minRows={3} margin="normal"
            inputProps={{ maxLength: REASON_MAX }} helperText={`${reason.length}/${REASON_MAX} · ${t("Ví dụ: quên mật khẩu sau kỳ nghỉ, cần vào hệ thống để xử lý hồ sơ.")}`} />
          <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
            {loading ? <CircularProgress size={22} color="inherit" /> : t("Gửi yêu cầu cho Admin")}
          </Button>
        </Box>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
