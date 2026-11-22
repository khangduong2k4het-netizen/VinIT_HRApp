'use client';

/**
 * Chuông thông báo lịch phỏng vấn.
 *
 * Vì sao cần: trước đó, đổi giờ một buổi phỏng vấn không báo cho ai. Người phỏng
 * vấn chỉ biết nếu tự mở trang lịch — và thường thì họ không mở, cho đến lúc đi
 * sai giờ. Đây là bản **trong ứng dụng**; email để sau (ghi trong `00041` và
 * trong `doc/DE_XUAT_LICH_PHONG_VAN.md`), nên component này cố ý không có nút
 * "gửi lại email".
 *
 * Không gộp vào badge việc-cần-làm: hai con số trả lời hai câu khác nhau ("có
 * bao nhiêu việc phải làm" và "có gì vừa thay đổi"), và badge việc-cần-làm đã
 * có đích riêng là dashboard.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Badge, Box, Button, Divider, IconButton, List, ListItem, ListItemButton, Menu, Stack, Tooltip, Typography } from '@mui/material';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import { useI18n } from '@/i18n/I18nProvider';
import { notificationsApi } from '@/lib/api';
import { notificationText } from '@/lib/notificationText';
import type { InterviewNotification } from '@/types';

// Hỏi lại mỗi 60 giây. Không dùng websocket: thông báo lịch phỏng vấn không cần
// độ trễ dưới một phút, và một kết nối thường trực cho mỗi tab là cái giá không
// tương xứng.
const POLL_MS = 60_000;

export default function NotificationBell() {
  const { t } = useI18n();
  const router = useRouter();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [items, setItems] = useState<InterviewNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const response = await notificationsApi.list();
      if (!mounted.current) return;
      setItems(response.data.items || []);
      setUnread(response.data.unread_count || 0);
    } catch {
      // Im lặng: chuông không tải được không phải lý do để làm phiền người dùng
      // bằng một banner lỗi. Lần hỏi sau sẽ thử lại.
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [load]);

  const open = (event: React.MouseEvent<HTMLElement>) => {
    setAnchor(event.currentTarget);
    void load();
  };

  const markAll = async () => {
    setBusy(true);
    try {
      await notificationsApi.markRead();
      await load();
    } finally { setBusy(false); }
  };

  const goTo = async (item: InterviewNotification) => {
    setAnchor(null);
    if (!item.read_at) {
      try { await notificationsApi.markRead([item.notification_id]); } catch { /* không chặn điều hướng */ }
    }
    router.push(`/interviews/${item.interview_id}`);
  };

  return (
    <>
      <Tooltip title={t('Thông báo')}>
        <IconButton color="inherit" onClick={open} aria-label={t('{0} thông báo chưa đọc', unread)} data-testid="notification-bell">
          <Badge badgeContent={unread > 99 ? '99+' : unread} color="warning">
            <NotificationsNoneIcon />
          </Badge>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}
        PaperProps={{ sx: { width: 380, maxHeight: 480 } }}>
        <Box sx={{ px: 2, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle2">{t('Thông báo')}</Typography>
          {unread > 0 && <Button size="small" onClick={() => void markAll()} disabled={busy}>{t('Đọc tất cả')}</Button>}
        </Box>
        <Divider />
        {!items.length ? (
          <Box sx={{ px: 2, py: 3 }}>
            <Typography variant="body2" color="text.secondary">
              {t('Chưa có thông báo nào. Thông báo xuất hiện khi lịch phỏng vấn của bạn thay đổi.')}
            </Typography>
          </Box>
        ) : (
          <List dense disablePadding>
            {items.map(item => (
              <ListItem key={item.notification_id} disablePadding>
                <ListItemButton onClick={() => void goTo(item)}
                  sx={{ bgcolor: item.read_at ? undefined : 'action.hover' }}>
                  <Stack spacing={0.25}>
                    <Typography variant="body2" fontWeight={item.read_at ? 400 : 700}>
                      {t(notificationText(item))}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {[item.position_code, item.position_title].filter(Boolean).join(' · ')}
                      {item.actor_name ? ` · ${t('bởi {0}', item.actor_name)}` : ''}
                    </Typography>
                  </Stack>
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
        <Divider />
        <Box sx={{ p: 1, textAlign: 'center' }}>
          {/* Nói rõ phạm vi ngay trên màn hình: người dùng không nên chờ email
              vì hệ thống chưa gửi email. */}
          <Typography variant="caption" color="text.secondary">
            {t('Thông báo chỉ hiện trong ứng dụng. Email sẽ được bổ sung sau.')}
          </Typography>
        </Box>
      </Menu>
    </>
  );
}
