'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import Link from 'next/link';
import { useI18n } from '@/i18n/I18nProvider';
import { scorecardsApi } from '@/lib/api';

type Reminder = { share_id: string; position_title: string; position_code: string; overdue_count: number; due_soon_count: number; earliest_due_at: string };
export default function ScorecardReminders({ refreshKey = 0 }: { refreshKey?: number }) {
  const { t, dateLocale } = useI18n();
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try { setLoading(true); const res = await scorecardsApi.reminders(); setReminders(res.data); setError(false); }
    catch { setError(true); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load, refreshKey]);
  return <Box sx={{ mb: 3 }}>
    <Typography variant="h2" sx={{ fontSize: 19, color: '#0A2B57', mb: 1 }}>{t('Nhắc hạn scorecard')}</Typography>
    <Typography variant="caption" color="text.secondary">{t('Hiển thị tối đa 100 shortlist đến hạn sớm nhất.')}</Typography>
    {loading ? <Typography variant="body2">{t('Đang tải nhắc hạn…')}</Typography> : error ? <Alert severity="warning" action={<Button color="inherit" onClick={load}>{t('Thử lại')}</Button>}>{t('Không thể tải nhắc hạn scorecard.')}</Alert> : reminders.length === 0 ? <Typography variant="body2" color="text.secondary">{t('Không có scorecard quá hạn hoặc đến hạn trong 24 giờ.')}</Typography> :
      <Stack spacing={1}>{reminders.map(r => <Card key={r.share_id} variant="outlined"><CardContent><Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ sm: 'center' }} spacing={1}>
        <Box sx={{ flex: 1 }}><Typography fontWeight={600}>{r.position_title} · {r.position_code}</Typography><Typography variant="caption">{t('Hạn gần nhất')}: {new Date(r.earliest_due_at).toLocaleString(dateLocale)}</Typography></Box>
        {r.overdue_count > 0 && <Chip color="error" size="small" label={t('Quá hạn: {0}', r.overdue_count)} />}
        {r.due_soon_count > 0 && <Chip color="warning" size="small" label={t('Đến hạn trong 24 giờ: {0}', r.due_soon_count)} />}
        <Button component={Link} href={`/shortlist?share=${encodeURIComponent(r.share_id)}`} size="small">{t('Xem shortlist')}</Button>
      </Stack></CardContent></Card>)}</Stack>}
  </Box>;
}
