'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Button, Card, CardContent, Typography } from '@mui/material';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { useI18n } from '@/i18n/I18nProvider';
import { authApi } from '@/lib/api';

// Two separate ways out, by role: people ask an Admin for a reset; an Admin who is locked out uses the recovery key.
export default function LoginHelpPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [recovery, setRecovery] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    authApi.publicConfig().then(response => { if (active) setRecovery(Boolean(response.data.admin_recovery)); }).catch(() => { if (active) setRecovery(false); });
    return () => { active = false; };
  }, []);

  const options = [
    {
      key: 'user',
      title: t("Tôi là HR / người dùng và quên mật khẩu"),
      text: t("Gửi yêu cầu kèm lý do cho Admin. Khi Admin duyệt, link đặt lại mật khẩu được gửi tới email của bạn."),
      action: t("Gửi yêu cầu cho Admin"),
      onClick: () => router.push('/forgot-password'),
      disabled: false,
    },
    {
      key: 'admin',
      title: t("Tôi là Admin và không đăng nhập được"),
      text: recovery === false
        ? t("Khôi phục Admin chưa được bật trên hệ thống này. Liên hệ người vận hành.")
        : t("Dùng mã khôi phục do người vận hành giữ để đặt mật khẩu mới. Không cần nhớ email."),
      action: t("Dùng mã khôi phục"),
      onClick: () => router.push('/admin-recovery'),
      disabled: recovery !== true,
    },
  ];

  return <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: '#F8FAFC', p: 2 }}>
    <Card sx={{ width: '100%', maxWidth: 520 }}><CardContent sx={{ p: { xs: 3, sm: 4 } }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>{t("Trợ giúp đăng nhập")}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>{t("Chọn đúng trường hợp của bạn.")}</Typography>
      <Box sx={{ display: 'grid', gap: 2 }}>
        {options.map(option => <Box key={option.key} sx={{ border: '1px solid #E4E7EC', borderRadius: 2, p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#0A2B57' }}>{option.title}</Typography>
          <Typography variant="body2" color="text.secondary">{option.text}</Typography>
          <Box><Button variant="outlined" color="secondary" disabled={option.disabled} onClick={option.onClick}>{option.action}</Button></Box>
        </Box>)}
      </Box>
      <Button fullWidth sx={{ mt: 3 }} onClick={() => router.push('/')}>{t("Quay lại đăng nhập")}</Button>
    </CardContent></Card>
  </Box>;
}
