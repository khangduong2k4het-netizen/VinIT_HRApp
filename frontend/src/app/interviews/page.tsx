'use client';

// Weekly interview schedule for HR & Hiring Managers ("Lịch phỏng vấn").
import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, Stack, Typography,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import TodayOutlinedIcon from '@mui/icons-material/TodayOutlined';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import Link from 'next/link';
import PageHeader from '@/components/common/PageHeader';
import EmptyState from '@/components/common/EmptyState';
import { interviewsApi, type InterviewFormat, type InterviewStatus } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type ScheduleItem = {
  session_id: string; application_id: string; position_id: string;
  position_code: string | null; position_title: string | null; candidate_name: string | null;
  round_no: number; title: string; session_status: InterviewStatus;
  starts_at: string; ends_at: string; slot_vn: string; format: InterviewFormat;
  location_or_link: string | null; probe_count: number;
  panelists: Array<{ user_id: string; display_name: string }>;
};

const STATUS_META: Record<InterviewStatus, { label: string; color: 'info' | 'success' | 'default' | 'warning' }> = {
  SCHEDULED: { label: 'Đã hẹn', color: 'info' },
  COMPLETED: { label: 'Đã hoàn thành', color: 'success' },
  CANCELLED: { label: 'Đã hủy', color: 'default' },
  NO_SHOW: { label: 'Không tham dự', color: 'warning' },
};

const FORMAT_LABELS: Record<InterviewFormat, string> = {
  ONLINE: 'Trực tuyến', ONSITE: 'Trực tiếp', PHONE: 'Điện thoại',
};

function mondayOf(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const diff = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - diff);
  return d;
}

function addDays(base: Date, days: number): Date {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

export default function InterviewsPage() {
  const { t, dateLocale } = useI18n();
  const [weekStart, setWeekStart] = useState<Date>(() => mondayOf(new Date()));
  const [items, setItems] = useState<ScheduleItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const weekEnd = useMemo(() => addDays(weekStart, 7), [weekStart]);

  const load = useCallback(async () => {
    setItems(null);
    setError(null);
    try {
      const res = await interviewsApi.mySchedule({
        from_date: weekStart.toISOString(),
        to_date: weekEnd.toISOString(),
      });
      setItems(res.data.items || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể tải lịch phỏng vấn.'));
      setItems([]);
    }
  }, [weekStart, weekEnd, t]);

  useEffect(() => { load(); }, [load]);

  const downloadIcs = async (item: ScheduleItem) => {
    try {
      const res = await interviewsApi.downloadIcs(item.session_id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interview-round-${item.round_no}.ics`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch {
      setError(t('Không thể tải file lịch .ics.'));
    }
  };

  const rangeLabel = `${weekStart.toLocaleDateString(dateLocale)} – ${addDays(weekStart, 6).toLocaleDateString(dateLocale)}`;
  const scheduledCount = (items || []).filter(i => i.session_status === 'SCHEDULED').length;
  const completedCount = (items || []).filter(i => i.session_status === 'COMPLETED').length;

  return (
    <Box>
      <PageHeader
        eyebrow={t('Tuyển dụng')}
        title={t('Lịch phỏng vấn')}
        description={t('Các buổi phỏng vấn trong tuần bạn tham gia hội đồng hoặc phụ trách tuyển dụng. Tải file .ics để thêm vào Outlook / Google Calendar.')}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <Button size="small" variant="outlined" startIcon={<ChevronLeftIcon />} onClick={() => setWeekStart(w => addDays(w, -7))}>
              {t('Tuần trước')}
            </Button>
            <Button size="small" variant="outlined" startIcon={<TodayOutlinedIcon />} onClick={() => setWeekStart(mondayOf(new Date()))}>
              {t('Tuần này')}
            </Button>
            <Button size="small" variant="outlined" endIcon={<ChevronRightIcon />} onClick={() => setWeekStart(w => addDays(w, 7))}>
              {t('Tuần sau')}
            </Button>
          </Stack>
        }
      />

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Card variant="outlined">
            <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
              <Typography variant="caption" color="text.secondary">{t('Khoảng thời gian')}</Typography>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mt: 0.5 }}>{rangeLabel}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Card variant="outlined">
            <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
              <Typography variant="caption" color="text.secondary">{t('Đã hẹn trong tuần')}</Typography>
              <Typography variant="h4" className="tabular-nums" sx={{ mt: 0.5, fontWeight: 700, color: 'primary.main' }}>
                {scheduledCount}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Card variant="outlined">
            <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
              <Typography variant="caption" color="text.secondary">{t('Đã hoàn thành')}</Typography>
              <Typography variant="h4" className="tabular-nums" sx={{ mt: 0.5, fontWeight: 700, color: 'success.main' }}>
                {completedCount}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}

      {items === null ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress size={28} /></Box>
      ) : items.length === 0 ? (
        <EmptyState
          title={t('Không có buổi phỏng vấn nào trong tuần này.')}
          description={t('Mở hồ sơ một ứng viên để đặt lịch phỏng vấn mới hoặc chuyển sang tuần khác.')}
        />
      ) : (
        <Stack spacing={1.5}>
          {items.map(item => (
            <Card key={item.session_id} variant="outlined">
              <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between" alignItems={{ sm: 'center' }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                      <Chip size="small" color="primary" label={t('Vòng {0}', item.round_no)} />
                      <Typography variant="subtitle1" fontWeight={700} color="primary.main">
                        {item.candidate_name || t('Hồ sơ ứng viên')}
                      </Typography>
                      <Chip size="small" variant="outlined" color={STATUS_META[item.session_status].color} label={t(STATUS_META[item.session_status].label)} />
                      <Chip size="small" variant="outlined" label={t(FORMAT_LABELS[item.format])} />
                      {item.probe_count > 0 && (
                        <Chip size="small" color="warning" variant="outlined" label={t('{0} điểm cần hỏi sâu', item.probe_count)} />
                      )}
                    </Stack>
                    <Typography variant="body2" fontWeight={600} sx={{ mt: 0.75 }}>{item.slot_vn}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                      {item.position_code ? `${item.position_code} · ` : ''}{item.position_title} — {item.title}
                    </Typography>
                    {item.location_or_link && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25, wordBreak: 'break-all' }}>
                        {t('Địa điểm / đường dẫn')}: {item.location_or_link}
                      </Typography>
                    )}
                    {item.panelists.length > 0 && (
                      <Stack direction="row" spacing={0.75} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>{t('Hội đồng:')}</Typography>
                        {item.panelists.map(p => <Chip key={p.user_id} size="small" variant="outlined" label={p.display_name} />)}
                      </Stack>
                    )}
                  </Box>
                  <Stack direction="row" spacing={1} flexShrink={0}>
                    <Button size="small" variant="outlined" startIcon={<CalendarMonthOutlinedIcon />} onClick={() => downloadIcs(item)}>
                      {t('Tải .ics')}
                    </Button>
                    <Button size="small" variant="contained" color="secondary" component={Link}
                      href={`/positions/${item.position_id}/applicants/${item.application_id}`}>
                      {t('Mở hồ sơ')}
                    </Button>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
}
