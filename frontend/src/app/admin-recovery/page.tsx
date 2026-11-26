'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, FormControlLabel, Radio, RadioGroup, Typography } from '@mui/material';
import PasswordField from '@/components/common/PasswordField';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

type AdminRow = { user_id: string; email: string; display_name: string; account_status: string };

// Step 1: the recovery key kept by whoever runs the system. Step 2: pick the Admin and choose a new password.
export default function AdminRecoveryPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [recoveryKey, setRecoveryKey] = useState('');
  const [admins, setAdmins] = useState<AdminRow[] | null>(null);
  const [selected, setSelected] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const detail = (err: any) => (typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : t("Không thể thực hiện. Vui lòng thử lại."));

  const checkKey = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    try {
      setLoading(true);
      const response = await authApi.recoveryAdmins(recoveryKey.trim());
      const items: AdminRow[] = response.data.items || [];
      setAdmins(items);
      const active = items.filter(item => item.account_status === 'ACTIVE');
      if (active.length === 1) setSelected(active[0].user_id);
    } catch (err: any) { setError(detail(err)); } finally { setLoading(false); }
  };

  const reset = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (!selected) { setError(t("Hãy chọn tài khoản Admin.")); return; }
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      await authApi.recoveryReset(recoveryKey.trim(), selected, password);
      setPassword(''); setConfirm(''); setRecoveryKey(''); setDone(true);
    } catch (err: any) { setError(detail(err)); } finally { setLoading(false); }
  };

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 500 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>{t("Khôi phục tài khoản Admin")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t("Nhập mã khôi phục do người vận hành hệ thống giữ. Bạn không cần nhớ email của Admin.")}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {done ? <Alert severity="success" sx={{ mb: 2 }}>{t("Đã đặt mật khẩu mới. Hãy đăng nhập bằng mật khẩu mới; các phiên đăng nhập cũ đã bị thu hồi.")}</Alert>
        : admins === null
          ? <Box component="form" onSubmit={checkKey}>
            <PasswordField label={t("Mã khôi phục")} value={recoveryKey} onChange={e => setRecoveryKey(e.target.value)} fullWidth required margin="normal" autoComplete="off" />
            <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading || !recoveryKey.trim()} sx={{ mt: 2 }}>
              {loading ? <CircularProgress size={22} color="inherit" /> : t("Tiếp tục")}
            </Button>
          </Box>
          : <Box component="form" onSubmit={reset}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{t("Chọn tài khoản Admin")}</Typography>
            <RadioGroup value={selected} onChange={e => setSelected(e.target.value)}>
              {admins.map(admin => <FormControlLabel key={admin.user_id} value={admin.user_id} disabled={admin.account_status !== 'ACTIVE'} control={<Radio />}
                label={<Box><Typography variant="body2" fontWeight={600} sx={{ overflowWrap: 'anywhere' }}>{admin.email}</Typography>
                  <Typography variant="caption" color="text.secondary">{admin.display_name}{admin.account_status !== 'ACTIVE' ? ` · ${t("Đã ngừng hoạt động")}` : ''}</Typography></Box>} />)}
            </RadioGroup>
            <PasswordField label={t("Mật khẩu mới")} value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
            <PasswordField label={t("Xác nhận mật khẩu")} value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
            <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
              {loading ? <CircularProgress size={22} color="inherit" /> : t("Đặt mật khẩu mới")}
            </Button>
          </Box>}
      <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
