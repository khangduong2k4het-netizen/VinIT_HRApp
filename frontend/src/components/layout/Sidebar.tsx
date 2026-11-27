'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import {
  Box, Divider, Drawer, IconButton, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Tooltip, Typography,
} from '@mui/material';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import PeopleOutlineIcon from '@mui/icons-material/PeopleOutline';
import SpaceDashboardOutlinedIcon from '@mui/icons-material/SpaceDashboardOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import ManageAccountsOutlinedIcon from '@mui/icons-material/ManageAccountsOutlined';
import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined';
import LibraryBooksOutlinedIcon from '@mui/icons-material/LibraryBooksOutlined';
import DeleteSweepOutlinedIcon from '@mui/icons-material/DeleteSweepOutlined';
import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import AutoGraphOutlinedIcon from '@mui/icons-material/AutoGraphOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import GroupsOutlinedIcon from '@mui/icons-material/GroupsOutlined';
import EventAvailableOutlinedIcon from '@mui/icons-material/EventAvailableOutlined';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import MoveToInboxOutlinedIcon from '@mui/icons-material/MoveToInboxOutlined';
import AlternateEmailOutlinedIcon from '@mui/icons-material/AlternateEmailOutlined';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { onUrlStateChange, recallPage, rememberPage, sectionFor } from '@/lib/navMemory';

const DRAWER_WIDTH = 248;
const DRAWER_COLLAPSED_WIDTH = 72;

const menuGroups = [
  {
    label: 'Công việc tuyển dụng',
    items: [
      { text: 'Tổng quan công việc', icon: <SpaceDashboardOutlinedIcon fontSize="small" />, href: '/dashboard' },
      { text: 'Vị trí tuyển dụng', icon: <WorkOutlineIcon fontSize="small" />, href: '/positions' },
      { text: 'Shortlist & phản hồi', icon: <PeopleOutlineIcon fontSize="small" />, href: '/shortlist' },
      { text: 'Lịch phỏng vấn', icon: <EventAvailableOutlinedIcon fontSize="small" />, href: '/interviews' },
      { text: 'Thư viện rubric', icon: <LibraryBooksOutlinedIcon fontSize="small" />, href: '/rubric-library', hrOnly: true },
      { text: 'Talent Pool', icon: <GroupsOutlinedIcon fontSize="small" />, href: '/talent-pool', hrOnly: true },
      { text: 'Hộp thư CV', icon: <MoveToInboxOutlinedIcon fontSize="small" />, href: '/mail-triage', hrOnly: true },
      { text: 'Mẫu thư ứng viên', icon: <MailOutlineIcon fontSize="small" />, href: '/email-templates', hrOnly: true },
    ],
  },
  {
    label: 'Phân tích & tuân thủ',
    hrGroupOnly: true,
    items: [
      { text: 'Báo cáo vận hành', icon: <InsightsOutlinedIcon fontSize="small" />, href: '/reports', hrOnly: true },
      { text: 'Chất lượng AI', icon: <AutoGraphOutlinedIcon fontSize="small" />, href: '/reports/ai-quality', hrOnly: true },
      { text: 'Kiểm định chất lượng', icon: <FactCheckOutlinedIcon fontSize="small" />, href: '/quality', leadOnly: true },
      { text: 'Lưu trữ & xóa dữ liệu', icon: <DeleteSweepOutlinedIcon fontSize="small" />, href: '/retention', hrOnly: true },
    ],
  },
  {
    label: 'Quản trị',
    adminOnly: true,
    items: [
      { text: 'Quản trị AI', icon: <SettingsOutlinedIcon fontSize="small" />, href: '/admin' },
      { text: 'Kết nối hộp thư', icon: <AlternateEmailOutlinedIcon fontSize="small" />, href: '/admin/mailbox' },
      { text: 'Quản lý tài khoản', icon: <ManageAccountsOutlinedIcon fontSize="small" />, href: '/admin/users' },
      { text: 'Quản lý phòng ban', icon: <ApartmentOutlinedIcon fontSize="small" />, href: '/admin/departments' },
      { text: 'Nhật ký audit', icon: <HistoryOutlinedIcon fontSize="small" />, href: '/admin/audit' },
    ],
  },
];

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
  isAdmin: boolean;
  isHr?: boolean;
  isLead?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function Sidebar({
  mobileOpen,
  onClose,
  isAdmin,
  isHr = false,
  isLead = false,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const sections = React.useMemo(() => menuGroups.flatMap(group => group.items.map(item => item.href)), []);
  // Remember the last page (with its filters) seen in each section.
  React.useEffect(() => {
    const record = (url: string) => {
      const section = sectionFor(url.split('?')[0], sections);
      if (section) rememberPage(section, url);
    };
    record(window.location.pathname + window.location.search);
    return onUrlStateChange(record);
  }, [pathname, sections]);
  // Clicking a section you are not in returns to where you left it; clicking the
  // section you are already in goes to its main list.
  const openSection = (event: React.MouseEvent, href: string) => {
    onClose();
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    if (sectionFor(pathname, sections) === href) return;
    const last = recallPage(href);
    if (last && last !== href) { event.preventDefault(); router.push(last); }
  };
  const width = collapsed ? DRAWER_COLLAPSED_WIDTH : DRAWER_WIDTH;

  const renderContent = (isCollapsed: boolean) => (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Brand header — Academic Light (clean crest on white with thin crimson rule) */}
      <Box
        sx={{
          height: 56,
          px: isCollapsed ? 1 : 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'space-between',
          borderBottom: '1px solid #E5EAF0',
          flexShrink: 0,
        }}
      >
        <Box
          component={Link}
          href="/dashboard"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            textDecoration: 'none',
            minWidth: 0,
          }}
        >
          <Box
            component="img"
            src="/vinuni-logo.png"
            alt="VinUniversity"
            sx={{ height: isCollapsed ? 24 : 28, width: 'auto', maxWidth: isCollapsed ? 40 : 124, objectFit: 'contain' }}
          />
          {!isCollapsed && (
            <Box sx={{ pl: 1, borderLeft: '1px solid #E2E8F0', lineHeight: 1.15 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 700, color: '#0A2B57', letterSpacing: '0.02em' }}>
                HRA
              </Typography>
              <Typography sx={{ fontSize: 10, fontWeight: 500, color: '#64748B' }}>
                CV Screening
              </Typography>
            </Box>
          )}
        </Box>
        {!isCollapsed && onToggleCollapse && (
          <Tooltip title={t('Thu gọn thanh bên')}>
            <IconButton
              size="small"
              onClick={onToggleCollapse}
              aria-label={t('Thu gọn thanh bên')}
              sx={{
                display: { xs: 'none', md: 'inline-flex' },
                width: 40,
                height: 40,
                color: '#64748B',
                '&:hover': { backgroundColor: '#F1F5F9', color: '#0A2B57' },
              }}
            >
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      {/* Collapsed: the way back is a clear button under the header, not only a tiny one in the footer */}
      {isCollapsed && onToggleCollapse && (
        <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1.5 }}>
          <Tooltip title={t('Mở rộng thanh bên')} placement="right">
            <IconButton
              onClick={onToggleCollapse}
              aria-label={t('Mở rộng thanh bên')}
              sx={{
                width: 40, height: 40, color: '#0A2B57', backgroundColor: '#FFFFFF', border: '1px solid #D5DCE6',
                '&:hover': { backgroundColor: '#EEF4FC', borderColor: '#0A2B57' },
              }}
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Navigation groups */}
      <List
        sx={{ pt: 1.5, pb: 2, px: 1, flexGrow: 1, overflowY: 'auto' }}
        component="nav"
        aria-label={t('Điều hướng chính')}
      >
        {menuGroups
          .filter(group => (!group.adminOnly || isAdmin) && (!group.hrGroupOnly || isHr || isLead))
          .map((group, groupIndex) => {
            const visibleItems = group.items.filter(
              item => (!('hrOnly' in item) || isHr) && (!('leadOnly' in item) || isLead),
            );
            if (!visibleItems.length) return null;
            return (
              <React.Fragment key={group.label}>
                {groupIndex > 0 && <Divider sx={{ my: 1.25, borderColor: '#EEF2F7' }} />}
                {!isCollapsed && (
                  <Typography
                    variant="overline"
                    sx={{
                      display: 'block',
                      px: 1.5,
                      pt: 0.75,
                      pb: 0.5,
                      color: '#64748B',
                      fontSize: 10.5,
                      letterSpacing: '0.06em',
                    }}
                  >
                    {t(group.label)}
                  </Typography>
                )}
                {visibleItems.map(item => {
                  const selected = ['/admin', '/reports'].includes(item.href)
                    ? pathname === item.href
                    : pathname.startsWith(item.href);
                  const button = (
                    <ListItemButton
                      component={Link}
                      href={item.href}
                      onClick={(e: React.MouseEvent) => openSection(e, item.href)}
                      selected={selected}
                      aria-current={selected ? 'page' : undefined}
                      sx={{
                        borderRadius: '8px',
                        minHeight: 38,
                        px: isCollapsed ? 0 : 1.5,
                        justifyContent: isCollapsed ? 'center' : 'flex-start',
                        position: 'relative',
                        color: selected ? '#0A2B57' : '#334155',
                        backgroundColor: selected ? '#EEF4FC' : 'transparent',
                        '&::before': selected
                          ? {
                              content: '""',
                              position: 'absolute',
                              left: 0,
                              top: 7,
                              bottom: 7,
                              width: 3,
                              borderRadius: '0 3px 3px 0',
                              backgroundColor: '#C72127',
                            }
                          : undefined,
                        '&.Mui-selected': {
                          backgroundColor: '#EEF4FC',
                          color: '#0A2B57',
                          '&:hover': { backgroundColor: '#E3EEFA' },
                          '& .MuiListItemIcon-root': { color: '#0A2B57' },
                        },
                        '&:hover': {
                          backgroundColor: '#F1F5F9',
                          color: '#0F172A',
                        },
                      }}
                    >
                      <ListItemIcon
                        sx={{
                          color: selected ? '#0A2B57' : '#64748B',
                          minWidth: isCollapsed ? 0 : 32,
                          justifyContent: 'center',
                        }}
                      >
                        {item.icon}
                      </ListItemIcon>
                      {!isCollapsed && (
                        <ListItemText
                          primary={t(item.text)}
                          primaryTypographyProps={{
                            fontSize: 13.5,
                            fontWeight: selected ? 600 : 500,
                            noWrap: true,
                          }}
                        />
                      )}
                    </ListItemButton>
                  );
                  return (
                    <ListItem key={item.href} disablePadding sx={{ mb: 0.35 }}>
                      {isCollapsed ? (
                        <Tooltip title={t(item.text)} placement="right">
                          {button}
                        </Tooltip>
                      ) : (
                        button
                      )}
                    </ListItem>
                  );
                })}
              </React.Fragment>
            );
          })}
      </List>

      {/* Footer / expand toggle */}
      <Box sx={{ borderTop: '1px solid #EEF2F7', p: 1.5, textAlign: 'center', flexShrink: 0 }}>
        {isCollapsed && onToggleCollapse ? (
          <Tooltip title={t('Mở rộng thanh bên')} placement="right">
            <IconButton
              size="small"
              onClick={onToggleCollapse}
              aria-label={t('Mở rộng thanh bên')}
              sx={{ width: 40, height: 40, color: '#64748B', '&:hover': { backgroundColor: '#F1F5F9', color: '#0A2B57' } }}
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: 11, display: 'block', lineHeight: 1.4 }}>
            © {new Date().getFullYear()} VinUniversity · {t('Nội bộ sử dụng')}
          </Typography>
        )}
      </Box>
    </Box>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
            backgroundColor: '#FFFFFF',
            borderRight: '1px solid #E5EAF0',
          },
        }}
      >
        {renderContent(false)}
      </Drawer>
      <Drawer
        variant="permanent"
        open
        sx={{
          display: { xs: 'none', md: 'block' },
          width,
          flexShrink: 0,
          transition: 'width 0.18s ease',
          '& .MuiDrawer-paper': {
            width,
            boxSizing: 'border-box',
            backgroundColor: '#FFFFFF',
            borderRight: '1px solid #E5EAF0',
            transition: 'width 0.18s ease',
            overflowX: 'hidden',
          },
        }}
      >
        {renderContent(collapsed)}
      </Drawer>
    </>
  );
}

export { DRAWER_WIDTH, DRAWER_COLLAPSED_WIDTH };
