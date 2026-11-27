'use client';

import PasswordField from '@/components/common/PasswordField';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { clearNavMemory } from '@/lib/navMemory';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Stack,
} from '@mui/material';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import { authApi } from '@/lib/api';

export default function LoginPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapAvailable, setBootstrapAvailable] = useState(false);
  const [config, setConfig] = useState({ self_registration: false });
  const router = useRouter();

  useEffect(() => {
    let active = true;
    authApi.bootstrapStatus().then(response => { if (active) setBootstrapAvailable(Boolean(response.data.available)); }).catch(() => {});
    authApi.publicConfig().then(response => { if (active) setConfig({ self_registration: Boolean(response.data.self_registration) }); }).catch(() => {});
    return () => { active = false; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await authApi.login(email, password);
      const { access_token } = response.data;

      localStorage.setItem('hra_access_token', access_token);
      clearNavMemory(); // never reopen pages remembered for a previous user

      // Temporary credentials can only reach the password-change screen.
      router.push(response.data.user?.must_change_password ? '/change-password' : '/positions');
    } catch (err: any) {
      setError(
        err.response?.data?.detail || t("Đăng nhập thất bại, vui lòng kiểm tra lại email và mật khẩu")
      );
    } finally {
      setLoading(false);
    }
  };

  const highlights = [
    { icon: <FactCheckOutlinedIcon fontSize="small" />, text: t('Chuẩn hóa tiêu chí theo JD') },
    { icon: <VerifiedUserOutlinedIcon fontSize="small" />, text: t('Đối chiếu bằng chứng minh bạch') },
    { icon: <ShieldOutlinedIcon fontSize="small" />, text: t('Tuân thủ quyền riêng tư & lưu trữ') },
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'minmax(380px, 46%) 1fr' },
        bgcolor: 'background.default',
      }}
    >
      {/* Editorial Academic Light Brand Panel */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          bgcolor: 'primary.main',
          color: '#FFFFFF',
          position: 'relative',
          overflow: 'hidden',
          borderRight: '4px solid',
          borderColor: 'secondary.main',
          backgroundImage:
            'radial-gradient(circle at 12% 18%, rgba(199, 33, 39, 0.22) 0%, transparent 45%), radial-gradient(circle at 88% 85%, rgba(255, 255, 255, 0.08) 0%, transparent 42%)',
        }}
      >
        <Box>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              bgcolor: '#FFFFFF',
              px: 2,
              py: 1,
              borderRadius: 2,
              boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
            }}
          >
            <Box component="img" src="/vinuni-logo.png" alt="VinUniversity Logo" sx={{ height: 34, width: 'auto' }} />
          </Box>
        </Box>

        <Box sx={{ maxWidth: 420 }}>
          <Typography
            variant="overline"
            sx={{ color: 'rgba(255,255,255,0.75)', letterSpacing: '0.12em', display: 'block', mb: 1.5 }}
          >
            {t('Nền tảng sàng lọc hồ sơ nội bộ')}
          </Typography>
          <Typography variant="h1" sx={{ fontSize: 32, lineHeight: 1.25, color: '#FFFFFF', mb: 2 }}>
            CV Screening Application
          </Typography>
          <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.82)', mb: 4, lineHeight: 1.65 }}>
            {t('Chấm điểm dựa trên bằng chứng từ CV, quy trình phê duyệt tiêu chí rõ ràng và bảo mật dữ liệu ứng viên.')}
          </Typography>

          <Stack spacing={1.75}>
            {highlights.map(item => (
              <Stack key={item.text} direction="row" spacing={1.5} alignItems="center">
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(255,255,255,0.12)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {item.icon}
                </Box>
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.92)', fontWeight: 500 }}>
                  {item.text}
                </Typography>
              </Stack>
            ))}
          </Stack>
        </Box>

        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)' }}>
          VinUniversity Human Resources Analytics
        </Typography>
      </Box>

      {/* Sign-in Column */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: { xs: 2.5, sm: 4 },
          position: 'relative',
        }}
      >
        <Box sx={{ position: 'absolute', top: 20, right: 24 }}>
          <LanguageSwitcher />
        </Box>

        <Card
          variant="outlined"
          sx={{
            width: '100%',
            maxWidth: 430,
            borderRadius: 3,
            boxShadow: '0 8px 32px rgba(15, 23, 42, 0.06)',
          }}
        >
          <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <Box
                component="img"
                src="/vinuni-logo.png"
                alt="VinUniversity Logo"
                sx={{ height: 48, width: 'auto', mb: 1.5, display: { xs: 'inline-block', md: 'none' } }}
              />
              <Typography variant="h2" sx={{ fontSize: 22, color: 'primary.main', mb: 0.75 }}>
                {t('Đăng nhập hệ thống')}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t("Dành cho HR Recruiter & Hiring Manager tại VinUniversity")}
              </Typography>
            </Box>

            {error && (
              <Alert severity="error" sx={{ mb: 2.5 }}>
                {t(error)}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                label="Email"
                type="email"
                fullWidth
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                margin="normal"
                placeholder="nguyenvana@vinuni.edu.vn"
              />
              <PasswordField
                label={t("Mật khẩu")}
                fullWidth
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                margin="normal"
                sx={{ mb: 3 }}
              />
              <Button
                type="submit"
                variant="contained"
                color="secondary"
                fullWidth
                size="large"
                disabled={loading}
                sx={{ py: 1.4 }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : t("Đăng nhập")}
              </Button>
            </form>

            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5, mt: 2 }}>
              <Button size="small" color="inherit" sx={{ color: 'text.secondary', textTransform: 'none' }} onClick={() => router.push('/login-help')}>
                {t("Cần trợ giúp đăng nhập?")}
              </Button>
              {config.self_registration && (
                <Button size="small" onClick={() => router.push('/register')}>
                  {t("Đăng ký tài khoản")}
                </Button>
              )}
            </Box>

            {bootstrapAvailable && (
              <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/bootstrap')}>
                {t("Khởi tạo Admin đầu tiên")}
              </Button>
            )}

            <Typography
              variant="caption"
              color="text.disabled"
              sx={{ display: 'block', textAlign: 'center', mt: 2.5 }}
            >
              © {new Date().getFullYear()} {t("VinUniversity. Nội bộ sử dụng.")}
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
