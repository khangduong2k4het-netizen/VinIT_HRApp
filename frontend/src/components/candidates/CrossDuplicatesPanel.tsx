'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Alert, Box, Button, Card, CardContent, Chip, Typography } from '@mui/material';
import { crossDuplicatesApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { REVIEW_LABELS } from '@/lib/reviewLabels';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';

type Match = { signal_id: string; signal_type: string; confidence: number; review_status: string;
  application_id: string; position_id: string; position_title: string; position_code: string;
  application_status: string; created_at: string; recruiters: { display_name: string }[] };
type Warnings = { matches: Match[]; has_restricted_matches: boolean };

export default function CrossDuplicatesPanel({ applicationId, versionKey }: { applicationId: string; versionKey?: string }) {
  const { t, dateLocale } = useI18n();
  const [data, setData] = useState<Warnings | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setData((await crossDuplicatesApi.list(applicationId)).data); setError(''); }
    catch { setError(t('Không thể tải cảnh báo trùng vị trí')); }
  }, [applicationId, t]);
  useEffect(() => { load(); }, [load, versionKey]);
  const run = async (action: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try { await action(); await load(); }
    catch { setError(t('Không thể cập nhật cảnh báo. Vui lòng tải lại.')); }
    finally { setBusy(false); }
  };
  return <Card sx={{ mb: 3 }}><CardContent>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
      <Typography variant="h6">{t('Hồ sơ trùng giữa các vị trí')}</Typography>
      <Button disabled={busy} onClick={() => run(() => crossDuplicatesApi.scan(applicationId))}>{t('Quét lại')}</Button>
    </Box>
    {error && <Alert severity="error">{error}</Alert>}
    {data?.has_restricted_matches && <Alert severity="warning" sx={{ my: 1 }}>{t('Có hồ sơ nghi trùng ở vị trí ngoài phạm vi của bạn. Chi tiết được bảo mật; liên hệ HR Lead để phối hợp.')}</Alert>}
    {data && !data.has_restricted_matches && !data.matches.length && <Typography color="text.secondary">{t('Chưa có cảnh báo trùng giữa các vị trí.')}</Typography>}
    {data?.matches.map(match => <Box key={match.signal_id} sx={{ borderTop: '1px solid #ddd', mt: 2, pt: 2 }}>
      <Typography component={Link} href={`/positions/${match.position_id}/applicants/${match.application_id}`}>{match.position_code} · {match.position_title}</Typography>
      <Typography variant="body2">{t(isApplicationStatus(match.application_status) ? APPLICATION_STATUSES[match.application_status].label : match.application_status)} · {new Date(match.created_at).toLocaleDateString(dateLocale)}</Typography>
      <Typography variant="body2">{t('HR phụ trách')}: {match.recruiters.map(r => r.display_name).join(', ') || '—'}</Typography>
      <Chip size="small" label={t(REVIEW_LABELS[match.signal_type] || match.signal_type)} sx={{ mr: 1 }} />
      <Chip size="small" label={t(match.review_status === 'PENDING' ? 'Chờ xác minh' : REVIEW_LABELS[match.review_status] || match.review_status)} />
      {match.review_status === 'PENDING' && <Box sx={{ mt: 1 }}>
        <Button disabled={busy} onClick={() => run(() => crossDuplicatesApi.review(match.signal_id, 'CONFIRMED'))}>{t('Xác nhận trùng')}</Button>
        <Button disabled={busy} onClick={() => run(() => crossDuplicatesApi.review(match.signal_id, 'DISMISSED'))}>{t('Không phải trùng')}</Button>
      </Box>}
    </Box>)}
    <Typography variant="caption" color="text.secondary">{t('Cảnh báo chỉ hỗ trợ phối hợp; hệ thống không tự gộp hoặc xóa hồ sơ.')}</Typography>
  </CardContent></Card>;
}
