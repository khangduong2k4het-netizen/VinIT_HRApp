'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { Alert, Box, Button, CircularProgress } from '@mui/material';
import { useRouter, usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import Sidebar from './Sidebar';
import Header, { APPBAR_HEIGHT } from './Header';
import { authApi } from '@/lib/api';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [systemRoles, setSystemRoles] = useState<string[]>([]);
  const [canAccessRubrics, setCanAccessRubrics] = useState(false);
  const [profile, setProfile] = useState<{ display_name?: string; email?: string } | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (['/', '/bootstrap', '/change-password'].includes(pathname)) { setIsLoading(false); setAuthenticated(false); return; }
    let active = true;
    const checkAuth = async () => {
      const token = localStorage.getItem('hra_access_token');
      if (!token) { router.replace('/'); return; }
      try {
        if (!authenticated) setIsLoading(true);
        const response = await authApi.me();
        if (active && response.data.must_change_password) {
          setAuthenticated(false); router.replace('/change-password'); return;
        }
        if (active) { setProfile(response.data); setSystemRoles(response.data.system_roles || []); setCanAccessRubrics((response.data.system_roles || []).some((r: string) => ['ADMIN', 'HR_LEAD', 'HR_RECRUITER'].includes(r)) || (response.data.position_assignments || []).some((p: { position_role: string }) => ['HR_RECRUITER', 'HR_LEAD'].includes(p.position_role))); setAuthenticated(true); setAuthError(null); }
      } catch (err: any) {
        if (active && err.response?.status !== 401) {
          setAuthenticated(false);
          setAuthError(err.response?.status === 403 ? (err.response?.data?.detail || t("Tài khoản không có quyền truy cập."))
            : t("Không thể kết nối máy chủ để xác thực. Vui lòng kiểm tra kết nối và thử lại."));
        }
      } finally { if (active) setIsLoading(false); }
    };
    checkAuth();
    return () => { active = false; };
    // Revalidate on navigation but do not include authenticated (would cause a loop).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, router, attempt]);

  if (['/', '/bootstrap', '/change-password'].includes(pathname)) return <>{children}</>;
  if (isLoading || (!authenticated && !authError)) return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', bgcolor: '#F8FAFC' }}>
      <CircularProgress color="secondary" aria-label={t("Đang xác thực")} />
    </Box>
  );
  if (authError) return (
    <Box sx={{ maxWidth: 560, mx: 'auto', mt: 8, p: 2 }}>
      <Alert severity="error" action={<Button color="inherit" onClick={() => setAttempt(n => n + 1)}>{t("Thử lại")}</Button>}>
        {t(authError)}
      </Alert>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} isAdmin={systemRoles.includes('ADMIN')} canAccessRubrics={canAccessRubrics} />
      <Header onOpenMenu={() => setMobileOpen(true)} profile={profile} />
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, backgroundColor: '#F8FAFC', minHeight: '100vh' }}>
        <Box sx={{ mt: `${APPBAR_HEIGHT}px`, p: { xs: 2, sm: 3, lg: 4 } }}>{children}</Box>
      </Box>
    </Box>
  );
}
