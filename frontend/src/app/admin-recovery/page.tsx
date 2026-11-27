'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, CircularProgress, FormControlLabel, Radio, RadioGroup, TextField, Typography } from '@mui/material';
import PasswordField from '@/components/common/PasswordField';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';
import { clearNavMemory } from '@/lib/navMemory';

type AdminRow = { user_id: string; email: string; display_name: string; account_status: string };
type Mode = 'choose' | 'key' | 'email';

// Two ways back in for an Admin: (a) the recovery key kept by whoever runs the system (no email needed),
// (b) a confirmation link emailed to the Admin's own address when the key is not at hand.
export default function AdminRecoveryPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('choose');
  const [recoveryKey, setRecoveryKey] = useState('');
  const [admins, setAdmins] = useState<AdminRow[] | null>(null);
  const [selected, setSelected] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [email, setEmail] = useState('');
  const [emailSent, setEmailSent] = useState<string | null>(null);
  const [emailCode, setEmailCode] = useState('');
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const detail = (err: any) => (typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : t("Không thể thực hiện. Vui lòng thử lại."));
  const back = () => { setMode('choose'); setError(null); setAdmins(null); setEmailSent(null); setEmailCode(''); setPassword(''); setConfirm(''); setResent(false); };

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

  const sendEmail = async (event?: React.FormEvent) => {
    event?.preventDefault(); setError(null);
    try {
      setLoading(true);
      const response = await authApi.recoveryEmailCode(email.trim());
      setEmailSent(response.data.message);
    } catch (err: any) { setError(detail(err)); } finally { setLoading(false); }
  };

  // Step 2 of the email path: the code from the mail is the "old password"; afterwards sign in straight away.
  const resetWithCode = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null);
    if (password !== confirm) { setError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
      setError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setLoading(true);
      await authApi.recoveryEmailReset(email.trim(), emailCode.trim(), password);
      await new Promise(resolve => setTimeout(resolve, 1300));  // a token issued in the same second as the reset is refused
      const login = await authApi.login(email.trim(), password);
      localStorage.setItem('hra_access_token', login.data.access_token);
      clearNavMemory();
      router.push('/positions');
    } catch (err: any) { setError(detail(err)); setLoading(false); }
  };

  const resend = async () => { setResent(false); await sendEmail(); setResent(true); };

  const option = (title: string, text: string, action: string, onClick: () => void) =>
    <Box sx={{ border: '1px solid #E4E7EC', borderRadius: 2, p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
      <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#0A2B57' }}>{title}</Typography>
      <Typography variant="body2" color="text.secondary">{text}</Typography>
      <Box><Button variant="outlined" color="secondary" onClick={onClick}>{action}</Button></Box>
    </Box>;

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 520 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>{t("Khôi phục tài khoản Admin")}</Typography>
      {error && <Alert severity="error" sx={{ my: 2 }}>{t(error)}</Alert>}

      {mode === 'choose' && <>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>{t("Chọn cách bạn muốn lấy lại quyền truy cập.")}</Typography>
        <Box sx={{ display: 'grid', gap: 2 }}>
          {option(t("Tôi có mã khôi phục"), t("Nhập mã do người vận hành giữ và đặt mật khẩu mới. Không cần nhớ email."), t("Nhập mã khôi phục"), () => setMode('key'))}
          {option(t("Tôi chưa có mã / làm mất mã"), t("Nhập email Admin. Hệ thống gửi một mã dùng một lần tới email đó; dùng mã này như mật khẩu cũ để đặt mật khẩu mới."), t("Nhập email Admin"), () => setMode('email'))}
        </Box>
      </>}

      {mode === 'key' && (done
        ? <Alert severity="success" sx={{ my: 2 }}>{t("Đã đặt mật khẩu mới. Hãy đăng nhập bằng mật khẩu mới; các phiên đăng nhập cũ đã bị thu hồi.")}</Alert>
        : admins === null
          ? <Box component="form" onSubmit={checkKey}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{t("Nhập mã khôi phục do người vận hành hệ thống giữ. Bạn không cần nhớ email của Admin.")}</Typography>
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
          </Box>)}

      {mode === 'email' && (emailSent === null
        ? <Box component="form" onSubmit={sendEmail}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t("Nhập email của tài khoản Admin. Hệ thống gửi tới email đó một mã dùng một lần (hết hạn sau 15 phút).")}
          </Typography>
          <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" autoComplete="username" />
          <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading} sx={{ mt: 2 }}>
            {loading ? <CircularProgress size={22} color="inherit" /> : t("Gửi mã tới email")}
          </Button>
        </Box>
        : <Box component="form" onSubmit={resetWithCode}>
          <Alert severity="info" sx={{ mb: 1 }}>{t(emailSent)}</Alert>
          {resent && <Alert severity="success" sx={{ mb: 1 }}>{t("Đã gửi lại mã (nếu email hợp lệ).")}</Alert>}
          <PasswordField label={t("Mật khẩu cũ (mã trong email, dùng 1 lần)")} value={emailCode} onChange={e => setEmailCode(e.target.value)} fullWidth required margin="normal" autoComplete="one-time-code" />
          <PasswordField label={t("Mật khẩu mới")} value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
          <PasswordField label={t("Xác nhận mật khẩu mới")} value={confirm} onChange={e => { setConfirm(e.target.value); setError(null); }} fullWidth required margin="normal" autoComplete="new-password" />
          <Button type="submit" variant="contained" color="secondary" fullWidth disabled={loading || !emailCode.trim()} sx={{ mt: 2 }}>
            {loading ? <CircularProgress size={22} color="inherit" /> : t("Đặt mật khẩu mới và đăng nhập")}
          </Button>
          <Button fullWidth size="small" sx={{ mt: 1 }} disabled={loading} onClick={resend}>{t("Gửi lại mã")}</Button>
        </Box>)}

      {mode !== 'choose' && !done && <Button fullWidth sx={{ mt: 2 }} onClick={back}>{t("Chọn cách khác")}</Button>}
      <Button fullWidth sx={{ mt: mode === 'choose' ? 3 : 1 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
