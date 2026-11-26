'use client';

import PasswordField from '@/components/common/PasswordField';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, Link, TextField, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

export default function RegisterPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [domains, setDomains] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  useEffect(() => {
    let active = true;
    authApi.publicConfig().then(response => {
      if (!active) return;
      setEnabled(Boolean(response.data.self_registration));
      if (!response.data.self_registration) router.replace('/');
      setDomains(response.data.registration_domains || []);
    }).catch(() => { if (active) { setEnabled(false); router.replace('/'); } });
    return () => { active = false; };
  }, [router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      const response = await authApi.register({ email: email.trim(), display_name: name.trim(), password });
      // Only present when the server runs in development without an email channel.
      setDevLink(response.data.dev_verify_link || null);
      setPassword(''); setConfirm(''); setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể gửi đăng ký."));
    } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 480 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>{t("Đăng ký tài khoản")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t("Tài khoản mới chỉ dùng được sau khi Admin duyệt và cấp vai trò.")}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {success ? <>
          <Alert severity="success" sx={{ mb: 2 }}>{t("Đã gửi đăng ký. Hãy mở liên kết xác minh trong email, sau đó chờ Admin duyệt.")}</Alert>
          {devLink && <Alert severity="warning" sx={{ mb: 2, overflowWrap: 'anywhere' }}>
            {t("Chế độ phát triển (chưa cấu hình email):")} <Link href={devLink}>{t("Mở liên kết xác minh email")}</Link>
          </Alert>}
        </>
        : enabled === null ? <CircularProgress size={24} aria-label={t("Đang kiểm tra")} />
        : enabled ? <Box component="form" onSubmit={submit}>
          {domains.length > 0 && <Alert severity="info" sx={{ mb: 1 }}>{t("Chỉ chấp nhận email thuộc tên miền:")} {domains.join(', ')}</Alert>}
          <TextField label={t("Họ và tên")} value={name} onChange={e => setName(e.target.value)} fullWidth required margin="normal" inputProps={{ maxLength: 120 }} />
          <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" autoComplete="username" />
          <PasswordField label={t("Mật khẩu")} value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
          <PasswordField label={t("Xác nhận mật khẩu")} value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
          <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
            {loading ? <CircularProgress size={22} color="inherit" /> : t("Gửi đăng ký")}
          </Button>
        </Box> : !error && <Alert severity="info" sx={{ mb: 2 }}>{t("Đăng ký tài khoản đang tắt. Liên hệ Admin để được cấp tài khoản.")}</Alert>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
