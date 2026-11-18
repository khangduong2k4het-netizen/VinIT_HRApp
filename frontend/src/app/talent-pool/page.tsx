'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from '@mui/material';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { POOL_REASONS } from '@/lib/talentPool';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';

type PoolItem = {
  application_id: string; candidate_name: string | null; application_status: string; position_id: string;
  position_code: string; position_title: string; reason_code: string; marked_at: string; expires_on: string;
};

/** P3-1: applications HR has put in the Talent Pool and that may still be reused. */
export default function TalentPoolPage() {
  const { t, dateLocale } = useI18n();
  const [items, setItems] = useState<PoolItem[] | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    try { setItems((await talentPoolApi.list()).data.items || []); setError(''); }
    catch (err: any) { setItems([]); setError(err.response?.data?.detail || t('Không thể tải Talent Pool')); }
  }, [t]);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items || []).filter(item => !q || `${item.candidate_name || ''} ${item.position_code} ${item.position_title}`
      .toLowerCase().includes(q));
  }, [items, query]);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>{t('Talent Pool')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('Hồ sơ HR đã đưa vào Talent Pool, ứng viên đồng ý cho dùng lại và còn trong thời hạn. Để quét cho vị trí mới, mở vị trí đó và bấm "Quét Talent Pool".')}
          </Typography>
        </Box>
        <Button variant="outlined" onClick={load}>{t('Làm mới')}</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      <Card><CardContent>
        <TextField size="small" fullWidth sx={{ mb: 2, maxWidth: 420 }} value={query} onChange={e => setQuery(e.target.value)}
          placeholder={t('Tìm theo tên ứng viên hoặc vị trí')} inputProps={{ 'aria-label': t('Tìm theo tên ứng viên hoặc vị trí') }} />
        {items === null ? <CircularProgress /> : filtered.length === 0 ? (
          <Typography color="text.secondary">{t('Chưa có hồ sơ nào trong Talent Pool.')}</Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('Ứng viên')}</TableCell>
                  <TableCell>{t('Vị trí đã ứng tuyển')}</TableCell>
                  <TableCell>{t('Trạng thái hồ sơ')}</TableCell>
                  <TableCell>{t('Lý do')}</TableCell>
                  <TableCell>{t('Ngày đưa vào')}</TableCell>
                  <TableCell>{t('Dùng lại đến')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.map(item => (
                  <TableRow key={item.application_id} hover>
                    <TableCell>
                      <Link href={`/positions/${item.position_id}/applicants/${item.application_id}`}>
                        {item.candidate_name || t('Chưa trích xuất tên')}
                      </Link>
                    </TableCell>
                    <TableCell>{item.position_code} · {item.position_title}</TableCell>
                    <TableCell>
                      <Chip size="small" label={isApplicationStatus(item.application_status)
                        ? t(APPLICATION_STATUSES[item.application_status].label) : item.application_status} />
                    </TableCell>
                    <TableCell>{t(POOL_REASONS[item.reason_code] || item.reason_code)}</TableCell>
                    <TableCell>{new Date(item.marked_at).toLocaleDateString(dateLocale)}</TableCell>
                    <TableCell>{item.expires_on}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent></Card>
    </Box>
  );
}
