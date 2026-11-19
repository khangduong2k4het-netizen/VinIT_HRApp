'use client';

// P3-1 Talent Pool: the pool HR handles, and scans of the pool against an open position.
import { useEffect, useState } from 'react';
import { Box, Card, CardContent, Chip, CircularProgress, MenuItem, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography, Alert } from '@mui/material';
import Link from 'next/link';
import { positionsApi, talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import ScanPanel from '@/components/talent-pool/ScanPanel';
import { MARK_REASONS, poolRef, type PoolMark } from '@/lib/talentPool';

export default function TalentPoolPage() {
  const { t } = useI18n();
  const [marks, setMarks] = useState<PoolMark[] | null>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [positionId, setPositionId] = useState('');

  useEffect(() => {
    talentPoolApi.marks().then(r => setMarks(r.data.items)).catch(() => setMarks([]));
    positionsApi.list('OPEN').then(r => setPositions(r.data)).catch(() => setPositions([]));
  }, []);

  return <Box>
    <Typography variant="h4" sx={{ mb: 1 }}>{t('Talent Pool')}</Typography>
    <Alert severity="info" sx={{ mb: 3 }}>
      {t('Chỉ gồm hồ sơ HR đã đưa vào pool, ứng viên đã đồng ý cho dùng ở vị trí khác và chưa rút, còn trong hạn 5 năm và không chờ xóa. Hệ thống chỉ gợi ý xếp hạng; HR quyết định liên hệ.')}
    </Alert>

    <Card sx={{ mb: 3 }}><CardContent>
      <Typography variant="h6" sx={{ mb: 2 }}>{t('Quét Talent Pool cho một vị trí')}</Typography>
      <TextField select size="small" label={t('Vị trí đang mở')} value={positionId} onChange={e => setPositionId(e.target.value)} sx={{ minWidth: 320, mb: 2 }}>
        {positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.title} · {p.position_code}</MenuItem>)}
      </TextField>
      {positionId && <ScanPanel key={positionId} positionId={positionId} />}
    </CardContent></Card>

    <Card><CardContent>
      <Typography variant="h6" sx={{ mb: 2 }}>{t('Hồ sơ trong Talent Pool')}</Typography>
      {marks === null ? <CircularProgress size={24} /> : marks.length === 0
        ? <Typography color="text.secondary">{t('Chưa có hồ sơ nào. Mở một hồ sơ đã shortlist hoặc phỏng vấn và bấm “Đưa vào Talent Pool”.')}</Typography>
        : <Table size="small">
          <TableHead><TableRow>
            <TableCell>{t('Hồ sơ')}</TableCell><TableCell>{t('Vị trí nguồn')}</TableCell><TableCell>{t('Lý do')}</TableCell>
            <TableCell>{t('Trạng thái')}</TableCell><TableCell>{t('Lưu đến')}</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {marks.map(m => <TableRow key={m.application_id}>
              <TableCell><Link href={`/positions/${m.position_id}/applicants/${m.application_id}`}>{poolRef(m.application_id)}</Link></TableCell>
              <TableCell>{m.position_title}<Typography variant="caption" display="block" color="text.secondary">{m.position_code}</Typography></TableCell>
              <TableCell>{t(MARK_REASONS[m.reason_code] || m.reason_code)}</TableCell>
              <TableCell>{m.eligible ? <Chip size="small" color="success" label={t('Có thể quét')} /> : <Chip size="small" color="warning" label={t('Không còn đủ điều kiện')} />}</TableCell>
              <TableCell>{m.expires_on || '—'}</TableCell>
            </TableRow>)}
          </TableBody>
        </Table>}
    </CardContent></Card>
  </Box>;
}
