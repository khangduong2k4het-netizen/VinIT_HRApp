'use client';

import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';

import * as React from 'react';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AppBar, Avatar, Badge, Box, Button, Divider, IconButton, Menu, MenuItem, Popover, Stack, Toolbar, Tooltip, Typography,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import KeyIcon from '@mui/icons-material/Key';
import LogoutIcon from '@mui/icons-material/Logout';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { usePathname, useRouter } from 'next/navigation';
import { DRAWER_WIDTH } from './Sidebar';
import { retentionApi } from '@/lib/api';

const APPBAR_HEIGHT = 56;

const ROUTE_TITLES: [string, string][] = [
  ['/reports/ai-quality', 'Chất lượng AI'],
  ['/reports', 'Báo cáo vận hành'],
  ['/dashboard', 'Tổng quan công việc'],
  ['/positions', 'Vị trí tuyển dụng'],
  ['/shortlist', 'Shortlist & phản hồi'],
  ['/rubric-library', 'Thư viện rubric'],
  ['/talent-pool', 'Talent Pool'],
  ['/quality', 'Kiểm định chất lượng'],
  ['/retention', 'Lưu trữ & xóa dữ liệu'],
  ['/admin/users', 'Quản lý tài khoản'],
  ['/admin/departments', 'Quản lý phòng ban'],
  ['/admin/audit', 'Nhật ký audit'],
  ['/admin', 'Quản trị AI'],
];

interface HeaderProps {
  onOpenMenu: () => void;
  profile?: { display_name?: string; email?: string } | null;
  drawerWidth?: number;
  isHr?: boolean;
}

type RetentionReminder = {
  notification_id: string;
  position_code: string;
  position_title: string;
  milestone_days: number;
  open_case_count: number;
  days_until_due: number | null;
};

export default function Header({ onOpenMenu, profile, drawerWidth = DRAWER_WIDTH, isHr = false }: HeaderProps) {
  const { t } = useI18n();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [bellAnchor, setBellAnchor] = useState<HTMLElement | null>(null);
  const [reminders, setReminders] = useState<RetentionReminder[]>([]);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isHr) return;
    let active = true;
    retentionApi.notifications(true)
      .then(res => { if (active && Array.isArray(res.data)) setReminders(res.data); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [isHr, pathname]);

  const markReminderRead = async (id: string) => {
    setReminders(prev => prev.filter(r => r.notification_id !== id));
    try { await retentionApi.markNotificationRead(id); } catch { /* ignore */ }
  };

  const handleLogout = () => {
    localStorage.removeItem('hra_access_token');
    setAnchor(null);
    router.replace('/');
  };

  const name = profile?.display_name || profile?.email || t('Tài khoản');
  const sectionLabel = ROUTE_TITLES.find(([prefix]) => pathname.startsWith(prefix))?.[1] || 'HR Resource Workspace';

  return (
    <AppBar
      position="fixed"
      sx={{
        height: APPBAR_HEIGHT,
        width: { xs: '100%', md: `calc(100% - ${drawerWidth}px)` },
        ml: { md: `${drawerWidth}px` },
        zIndex: theme => theme.zIndex.drawer + 1,
        backgroundColor: 'rgba(255, 255, 255, 0.88)',
        backdropFilter: 'blur(10px)',
        color: '#0F172A',
        borderBottom: '1px solid #E5EAF0',
        boxShadow: 'none',
        transition: 'width 0.18s ease, margin-left 0.18s ease',
      }}
    >
      <Toolbar sx={{ minHeight: `${APPBAR_HEIGHT}px !important`, px: { xs: 1.5, sm: 2.5 }, gap: 1.25 }}>
        <IconButton
          color="inherit"
          onClick={onOpenMenu}
          aria-label={t('Mở menu điều hướng')}
          edge="start"
          sx={{ display: { xs: 'inline-flex', md: 'none' }, color: '#334155' }}
        >
          <MenuIcon fontSize="small" />
        </IconButton>

        {/* Crisp breadcrumb */}
        <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography
            variant="caption"
            sx={{ color: '#64748B', fontWeight: 500, display: { xs: 'none', sm: 'inline' } }}
          >
            VinUni HRA
          </Typography>
          <Typography
            variant="caption"
            sx={{ color: '#CBD5E1', display: { xs: 'none', sm: 'inline' } }}
            aria-hidden
          >
            /
          </Typography>
          <Typography
            variant="body2"
            noWrap
            sx={{ color: '#0F172A', fontWeight: 600, fontSize: 13.5 }}
          >
            {t(sectionLabel)}
          </Typography>
        </Box>

        {/* Retention reminders bell (HR only) */}
        {isHr && (
          <>
            <Tooltip title={t('Thông báo lưu trữ & xóa dữ liệu')}>
              <IconButton
                size="small"
                onClick={e => setBellAnchor(e.currentTarget)}
                aria-label={t('Thông báo lưu trữ & xóa dữ liệu')}
                sx={{
                  color: '#475569',
                  border: '1px solid #E5EAF0',
                  borderRadius: '8px',
                  width: 34,
                  height: 34,
                  '&:hover': { backgroundColor: '#F1F5F9', color: '#0A2B57' },
                }}
              >
                <Badge badgeContent={reminders.length} color="secondary" max={9}>
                  <NotificationsNoneOutlinedIcon sx={{ fontSize: 19 }} />
                </Badge>
              </IconButton>
            </Tooltip>
            <Popover
              open={Boolean(bellAnchor)}
              anchorEl={bellAnchor}
              onClose={() => setBellAnchor(null)}
              anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
              transformOrigin={{ horizontal: 'right', vertical: 'top' }}
              PaperProps={{
                sx: { mt: 1, width: 340, borderRadius: '12px', border: '1px solid #E5EAF0', boxShadow: '0 14px 36px rgba(15,23,42,0.12)' },
              }}
            >
              <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid #EEF2F7', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0F172A' }}>
                  {t('Nhắc hạn lưu trữ')}
                </Typography>
                <Button component={Link} href="/retention" size="small" onClick={() => setBellAnchor(null)}>
                  {t('Xem tất cả')}
                </Button>
              </Box>
              {reminders.length === 0 ? (
                <Box sx={{ p: 2.5, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">{t('Không có thông báo chưa đọc.')}</Typography>
                </Box>
              ) : (
                <Stack divider={<Divider />} sx={{ maxHeight: 320, overflowY: 'auto' }}>
                  {reminders.slice(0, 6).map(item => (
                    <Box key={item.notification_id} sx={{ px: 2, py: 1.25 }}>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: '#0F172A' }}>
                        {item.position_code} · {item.position_title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" display="block">
                        {t('{0} hồ sơ chờ xử lý · mốc {1} ngày', item.open_case_count, item.milestone_days)}
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 0.75 }}>
                        <Button size="small" component={Link} href="/retention" onClick={() => setBellAnchor(null)}>
                          {t('Mở hàng đợi')}
                        </Button>
                        <Button size="small" color="inherit" onClick={() => markReminderRead(item.notification_id)}>
                          {t('Đã đọc')}
                        </Button>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </Popover>
          </>
        )}

        <LanguageSwitcher />

        {/* User profile pill */}
        <Tooltip title={t('Tài khoản')}>
          <Button
            onClick={event => setAnchor(event.currentTarget)}
            aria-label={t('Mở menu tài khoản')}
            aria-haspopup="menu"
            aria-expanded={!!anchor}
            endIcon={<KeyboardArrowDownIcon sx={{ fontSize: 16, color: '#64748B' }} />}
            sx={{
              p: '3px 8px 3px 4px',
              minWidth: 0,
              borderRadius: '999px',
              border: '1px solid #E5EAF0',
              backgroundColor: '#FFFFFF',
              color: '#0F172A',
              '&:hover': { backgroundColor: '#F8FAFC', borderColor: '#CBD5E1' },
            }}
          >
            <Avatar
              sx={{
                width: 28,
                height: 28,
                backgroundColor: '#0A2B57',
                fontSize: 12,
                fontWeight: 700,
                mr: { xs: 0, sm: 1 },
              }}
            >
              {name.charAt(0).toUpperCase()}
            </Avatar>
            <Typography
              variant="body2"
              noWrap
              sx={{
                display: { xs: 'none', sm: 'block' },
                maxWidth: 140,
                fontSize: 13,
                fontWeight: 600,
                color: '#0F172A',
              }}
            >
              {name}
            </Typography>
          </Button>
        </Tooltip>
      </Toolbar>

      <Menu
        anchorEl={anchor}
        open={!!anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        PaperProps={{
          sx: {
            mt: 1,
            minWidth: 230,
            borderRadius: '12px',
            border: '1px solid #E5EAF0',
            boxShadow: '0 14px 36px rgba(15,23,42,0.12)',
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.25 }}>
          <Typography variant="body2" fontWeight={700} color="#0F172A">{name}</Typography>
          {profile?.email && (
            <Typography variant="caption" color="text.secondary">{profile.email}</Typography>
          )}
        </Box>
        <Divider />
        <MenuItem
          onClick={() => { setAnchor(null); router.push('/change-password'); }}
          sx={{ gap: 1.25, py: 1, fontSize: 13.5 }}
        >
          <KeyIcon fontSize="small" sx={{ color: '#64748B' }} />
          {t('Đổi mật khẩu')}
        </MenuItem>
        <MenuItem
          onClick={handleLogout}
          sx={{ gap: 1.25, py: 1, fontSize: 13.5, color: 'error.main' }}
        >
          <LogoutIcon fontSize="small" />
          {t('Đăng xuất')}
        </MenuItem>
      </Menu>
    </AppBar>
  );
}

export { APPBAR_HEIGHT };
