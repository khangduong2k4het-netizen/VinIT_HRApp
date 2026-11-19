'use client';

import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';

import * as React from 'react';
import { useState } from 'react';
import { AppBar, Avatar, Box, Divider, IconButton, Menu, MenuItem, Toolbar, Tooltip, Typography } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import KeyIcon from '@mui/icons-material/Key';
import LogoutIcon from '@mui/icons-material/Logout';
import { useRouter } from 'next/navigation';
import { DRAWER_WIDTH } from './Sidebar';

const APPBAR_HEIGHT = 64;

interface HeaderProps {
  onOpenMenu: () => void;
  profile?: { display_name?: string; email?: string } | null;
}

export default function Header({ onOpenMenu, profile }: HeaderProps) {
  const { t } = useI18n();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem('hra_access_token');
    setAnchor(null);
    router.replace('/');
  };
  const name = profile?.display_name || profile?.email || t("Tài khoản");
  return (
    <AppBar position="fixed" sx={{ height: APPBAR_HEIGHT, width: { xs: '100%', md: `calc(100% - ${DRAWER_WIDTH}px)` },
      ml: { md: `${DRAWER_WIDTH}px` }, zIndex: theme => theme.zIndex.drawer + 1, backgroundColor: '#0A2B57', boxShadow: '0 1px 3px rgba(0,0,0,.1)' }}>
      <Toolbar sx={{ minHeight: `${APPBAR_HEIGHT}px !important`, gap: 1.5 }}>
        <IconButton color="inherit" onClick={onOpenMenu} aria-label={t("Mở menu điều hướng")} edge="start" sx={{ display: { xs: 'inline-flex', md: 'none' } }}><MenuIcon /></IconButton>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ color: '#fff', fontWeight: 700 }}>HR Resource Workspace</Typography>
        </Box>
        <LanguageSwitcher light />
        <Tooltip title={t("Tài khoản")}>
          <IconButton onClick={event => setAnchor(event.currentTarget)} aria-label={t("Mở menu tài khoản")} aria-haspopup="menu" aria-expanded={!!anchor}>
            <Avatar sx={{ width: 36, height: 36, backgroundColor: '#C72127', fontSize: 14, fontWeight: 700 }}>{name.charAt(0).toUpperCase()}</Avatar>
          </IconButton>
        </Tooltip>
      </Toolbar>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }} transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        PaperProps={{ sx: { mt: 1, minWidth: 220, borderRadius: 2 } }}>
        <Box sx={{ px: 2, py: 1 }}><Typography variant="body2" fontWeight={700}>{name}</Typography>
          {profile?.email && <Typography variant="caption" color="text.secondary">{profile.email}</Typography>}</Box>
        <Divider />
        <MenuItem onClick={() => { setAnchor(null); router.push('/change-password'); }} sx={{ gap: 1 }}><KeyIcon fontSize="small" />{t("Đổi mật khẩu")}</MenuItem>
        <MenuItem onClick={handleLogout} sx={{ gap: 1, color: 'error.main' }}><LogoutIcon fontSize="small" />{t("Đăng xuất")}</MenuItem>
      </Menu>
    </AppBar>
  );
}

export { APPBAR_HEIGHT };
