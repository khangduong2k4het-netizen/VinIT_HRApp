'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { Box, Divider, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography } from '@mui/material';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import WorkIcon from '@mui/icons-material/Work';
import PeopleIcon from '@mui/icons-material/People';
import BarChartIcon from '@mui/icons-material/BarChart';
import SettingsIcon from '@mui/icons-material/Settings';
import ManageAccountsIcon from '@mui/icons-material/ManageAccounts';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import ApartmentIcon from '@mui/icons-material/Apartment';
import EventIcon from '@mui/icons-material/Event';
import CategoryIcon from '@mui/icons-material/Category';
import { usePathname } from 'next/navigation';
import Link from 'next/link';

const DRAWER_WIDTH = 260;
const menuGroups = [
  {
    label: 'Công việc tuyển dụng',
    items: [
      { text: 'Tổng quan công việc', icon: <BarChartIcon />, href: '/dashboard' },
      { text: 'Vị trí tuyển dụng', icon: <WorkIcon />, href: '/positions' },
      { text: 'Gmail thử nghiệm', icon: <PeopleIcon />, href: '/gmail-test', hrOnly: true },
      { text: 'Email offline (demo)', icon: <PeopleIcon />, href: '/email-demo', hrOnly: true },
      { text: 'Talent Pool', icon: <PeopleIcon />, href: '/talent-pool', hrOnly: true },
      { text: 'Talent Pool (demo)', icon: <PeopleIcon />, href: '/talent-pool-demo', hrOnly: true },
      { text: 'Thư viện rubric', icon: <LibraryBooksIcon />, href: '/rubrics', hrOnly: true },
      { text: 'Shortlist & phản hồi', icon: <PeopleIcon />, href: '/shortlist' },
      { text: 'Lịch phỏng vấn', icon: <EventIcon />, href: '/interviews' },
      { text: 'Dữ liệu & lưu trữ', icon: <DeleteSweepIcon />, href: '/data-retention', hrOnly: true },
    ],
  },
  {
    label: 'Hệ thống',
    adminOnly: true,
    items: [
      { text: 'Quản trị hệ thống', icon: <SettingsIcon />, href: '/admin' },
      { text: 'Quản lý tài khoản', icon: <ManageAccountsIcon />, href: '/admin/users' },
      { text: 'Quản lý phòng ban', icon: <ApartmentIcon />, href: '/admin/departments' },
      { text: 'Quản lý nhóm vị trí', icon: <CategoryIcon />, href: '/admin/job-families' },
    ],
  },
];

export default function Sidebar({ mobileOpen, onClose, isAdmin, canAccessRubrics }: { mobileOpen: boolean; onClose: () => void; isAdmin: boolean; canAccessRubrics: boolean }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const content = (
    <>
      <Box sx={{ p: 3, pb: 2 }}>
        <Box sx={{ backgroundColor: '#fff', borderRadius: 1.5, px: 2, py: 1.5, mb: 1.5, display: 'flex', justifyContent: 'center' }}>
          <Box component="img" src="/vinuni-logo.png" alt="VinUniversity" sx={{ height: 32, width: 'auto', maxWidth: '100%' }} />
        </Box>
        <Typography variant="overline" sx={{ color: 'rgba(255,255,255,.75)', display: 'block', textAlign: 'center' }}>CV Screening Application</Typography>
      </Box>
      <Divider sx={{ borderColor: 'rgba(255,255,255,.12)' }} />
      <List sx={{ pt: 2 }} component="nav" aria-label={t("Điều hướng chính")}>
        {menuGroups.filter(group => !group.adminOnly || isAdmin).map(group => (
          <React.Fragment key={group.label}>
            <Typography variant="overline" sx={{ display: 'block', px: 3, pt: 1.5, pb: 0.75, color: 'rgba(255,255,255,.62)', fontSize: 10 }}>
              {t(group.label)}
            </Typography>
            {group.items.filter(item => !('hrOnly' in item) || !item.hrOnly || canAccessRubrics).map(item => {
              const selected = item.href === '/admin' ? pathname === '/admin' : (pathname === item.href || pathname.startsWith(`${item.href}/`));
              return (
                <ListItem key={item.href} disablePadding sx={{ mb: 0.5 }}>
                  <ListItemButton component={Link} href={item.href} onClick={onClose} selected={selected}
                    aria-current={selected ? 'page' : undefined}
                    sx={{ mx: 1, borderRadius: 2, minHeight: 46, transition: 'background-color .18s ease',
                      '&.Mui-selected': { backgroundColor: '#941616', '&:hover': { backgroundColor: '#7a1212' }, '& .MuiListItemIcon-root': { color: 'white' } },
                      '&:hover': { backgroundColor: 'rgba(255,255,255,.08)' } }}>
                    <ListItemIcon sx={{ color: 'rgba(255,255,255,.75)', minWidth: 40 }}>{item.icon}</ListItemIcon>
                    <ListItemText primary={t(item.text)} primaryTypographyProps={{ fontSize: 14, fontWeight: 500 }} />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </React.Fragment>
        ))}
      </List>
      <Box sx={{ flexGrow: 1 }} />
      <Box sx={{ p: 2, textAlign: 'center' }}><Typography variant="caption" sx={{ color: 'rgba(255,255,255,.5)' }}>© {new Date().getFullYear()} VinUniversity<br />{t("Nội bộ sử dụng")}</Typography></Box>
    </>
  );
  const paper = { width: DRAWER_WIDTH, boxSizing: 'border-box', borderRight: 'none', backgroundColor: '#0A2B57', color: 'white' } as const;
  return (
    <>
      <Drawer variant="temporary" open={mobileOpen} onClose={onClose} ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': paper }}>{content}</Drawer>
      <Drawer variant="permanent" open sx={{ display: { xs: 'none', md: 'block' }, width: DRAWER_WIDTH, flexShrink: 0, '& .MuiDrawer-paper': paper }}>
        {content}
      </Drawer>
    </>
  );
}

export { DRAWER_WIDTH };
