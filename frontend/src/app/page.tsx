'use client';

import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import { authApi } from '@/lib/api';

export default function LoginPage() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapAvailable, setBootstrapAvailable] = useState(false);
  const router = useRouter();

  useEffect(() => {
    let active = true;
    authApi.bootstrapStatus().then(response => { if (active) setBootstrapAvailable(Boolean(response.data.available)); }).catch(() => {});
    return () => { active = false; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await authApi.login(email, password);
      const { access_token } = response.data;

      // Store token in localStorage for MVP Phase 1
      localStorage.setItem('hra_access_token', access_token);

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

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#F8FAFC',
        backgroundImage:
          'linear-gradient(135deg, rgba(10, 43, 87, 0.05) 0%, rgba(199, 33, 39, 0.05) 100%)',
        p: 2,
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 420, boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}><LanguageSwitcher /></Box>
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            {/* VinUni Logo */}
            <Box
              component="img"
              src="/vinuni-logo.png"
              alt="VinUniversity Logo"
              sx={{ height: 56, width: 'auto', mb: 2 }}
            />
            <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 1 }}>
              CV Screening Application
            </Typography>
            <Typography variant="body2" color="text.secondary">{t("Dành cho HR Recruiter & Hiring Manager tại VinUniversity")}</Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
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
            <TextField
              label={t("Mật khẩu")}
              type="password"
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
              sx={{ py: 1.5 }}
            >
              {loading ? <CircularProgress size={24} color="inherit" /> : t("Đăng nhập")}
            </Button>
          </form>

          {bootstrapAvailable && <Button fullWidth sx={{ mt: 2 }} onClick={() => router.push('/bootstrap')}>
            {t("Khởi tạo Admin đầu tiên")}
          </Button>}

          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ display: 'block', textAlign: 'center', mt: 3 }}
          >
            © {new Date().getFullYear()} {t("VinUniversity. Nội bộ sử dụng.")}</Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
