'use client';

import PasswordField from '@/components/common/PasswordField';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

export default function BootstrapPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [available, setAvailable] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  useEffect(() => {
    let active = true;
    authApi.bootstrapStatus().then(response => { if (active) setAvailable(Boolean(response.data.available)); })
      .catch(() => { if (active) { setAvailable(false); setError(t("Không thể kiểm tra trạng thái khởi tạo.")); } });
    return () => { active = false; };
  }, [t]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      await authApi.bootstrap({ email: email.trim(), display_name: name.trim(), password, setup_token: token });
      setPassword(''); setConfirm(''); setToken(''); setSuccess(true); setAvailable(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể khởi tạo Admin."));
    } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 540 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Khởi tạo Admin đầu tiên")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>{t("Bước thiết lập này chỉ thực hiện một lần cho hệ thống.")}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {success ? <Alert severity="success" sx={{ mb: 2 }}>{t("Đã tạo Admin. Hãy đăng nhập bằng tài khoản vừa tạo.")}</Alert>
        : available === null ? <CircularProgress size={24} aria-label={t("Đang kiểm tra")} />
        : available ? <>
          <Alert severity="warning" sx={{ mb: 2 }}>{t("Chỉ thiết lập qua HTTPS và mạng tin cậy; mã khởi tạo do người vận hành cấp.")}</Alert>
          <Box component="form" onSubmit={submit}>
            <TextField label={t("Họ và tên")} value={name} onChange={e => setName(e.target.value)} fullWidth required margin="normal" inputProps={{ maxLength: 120 }} />
            <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" autoComplete="username" />
            <TextField label={t("Mã khởi tạo")} type="password" value={token} onChange={e => setToken(e.target.value)} fullWidth required margin="normal" autoComplete="off" inputProps={{ minLength: 32, maxLength: 256 }} />
            <PasswordField label={t("Mật khẩu Admin")} value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
            <PasswordField label={t("Xác nhận mật khẩu")} value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
            <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
              {loading ? <CircularProgress size={22} color="inherit" /> : t("Tạo Admin")}
            </Button>
          </Box>
        </> : !error && <Alert severity="info" sx={{ mb: 2 }}>{t("Khởi tạo Admin không khả dụng hoặc đã hoàn tất. Liên hệ người vận hành nếu cần hỗ trợ.")}</Alert>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
