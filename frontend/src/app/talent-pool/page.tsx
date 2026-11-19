'use client';

// P3-1 Talent Pool: the pool HR handles, and scans of the pool against an open position.
// Rules-only scoring: no CV text is sent to an AI provider. No names or contact data are shown.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, ButtonGroup, Card, CardContent, Chip, CircularProgress, Collapse, MenuItem, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import Link from 'next/link';
import { positionsApi, talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { DECISIONS, MARK_REASONS, OUTCOMES, SKIP_REASONS, poolRef, scoreText,
  scanIsActive, type PoolMark, type ScanDetail, type ScanResult, type ScanSummary } from '@/lib/talentPool';

function serverError(err: any, locale: 'vi' | 'en', fallback: string): string {
  const detail = err?.response?.data?.detail;
  return typeof detail === 'string' ? localizeServerMessage(detail, locale) : fallback;
}

function ResultRow({ result, scanId, onDecided }: { result: ScanResult; scanId: string; onDecided: () => void }) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const decide = async (decision: 'CONTACT' | 'SKIP' | 'LATER') => {
    setBusy(true); setError('');
    try { await talentPoolApi.decide(scanId, result.application_id, decision); onDecided(); }
    catch (err: any) { setError(serverError(err, locale, t('Không thể lưu quyết định'))); }
    finally { setBusy(false); }
  };
  return <>
    <TableRow hover>
      <TableCell>{result.rank}</TableCell>
      <TableCell>
        <Button size="small" onClick={() => setOpen(!open)}>{poolRef(result.application_id)}</Button>
        <Typography variant="caption" display="block" color="text.secondary">
          {t('Từ vị trí')}: {result.source_position_title} · {result.source_position_code}
        </Typography>
      </TableCell>
      <TableCell>{scoreText(result.matching_score)}</TableCell>
      <TableCell>{Math.round(result.evidence_coverage * 100)}%</TableCell>
      <TableCell>{result.unresolved_count}</TableCell>
      <TableCell>{result.pool_expires_on}</TableCell>
      <TableCell>
        <ButtonGroup size="small" disabled={busy}>
          {(['CONTACT', 'LATER', 'SKIP'] as const).map(d => (
            <Button key={d} variant={result.hr_decision === d ? 'contained' : 'outlined'} onClick={() => decide(d)}>{t(DECISIONS[d])}</Button>
          ))}
        </ButtonGroup>
        {error && <Typography variant="caption" color="error" display="block">{error}</Typography>}
      </TableCell>
    </TableRow>
    <TableRow>
      <TableCell colSpan={7} sx={{ py: 0, borderBottom: open ? undefined : 'none' }}>
        <Collapse in={open} unmountOnExit>
          <Box sx={{ py: 1.5 }}>
            {result.criterion_results.map(c => (
              <Box key={c.criterion_id} sx={{ mb: 1 }}>
                <Typography variant="body2"><strong>{c.name}</strong> · {t(OUTCOMES[c.outcome] || c.outcome)}</Typography>
                {c.quote
                  ? <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>“{c.quote}”</Typography>
                  : <Typography variant="caption" color="text.secondary">{t('Không có trích dẫn; HR cần kiểm tra trong hồ sơ gốc.')}</Typography>}
              </Box>
            ))}
            <Link href={`/positions/${result.source_position_id}/applicants/${result.application_id}`}>{t('Mở hồ sơ gốc (nếu bạn có quyền ở vị trí nguồn)')}</Link>
          </Box>
        </Collapse>
      </TableCell>
    </TableRow>
  </>;
}

export default function TalentPoolPage() {
  const { t, locale } = useI18n();
  const [marks, setMarks] = useState<PoolMark[] | null>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [positionId, setPositionId] = useState('');
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    talentPoolApi.marks().then(r => setMarks(r.data.items)).catch(() => setMarks([]));
    positionsApi.list('OPEN').then(r => setPositions(r.data)).catch(() => setPositions([]));
  }, []);

  const loadScan = useCallback(async (scanId: string) => {
    try { setScan((await talentPoolApi.scanDetail(scanId)).data); }
    catch (err: any) { setError(serverError(err, locale, t('Không thể tải kết quả quét'))); }
  }, [locale, t]);

  useEffect(() => {
    setScan(null); setScans([]); setError('');
    if (!positionId) return;
    talentPoolApi.scans(positionId).then(r => {
      setScans(r.data.items);
      if (r.data.items.length) loadScan(r.data.items[0].scan_id);
    }).catch(() => setScans([]));
  }, [positionId, loadScan]);

  // The worker scores the pool in the background: poll until the scan leaves PENDING/PROCESSING.
  const active = scanIsActive(scan?.status);
  useEffect(() => {
    if (!active || !scan) return;
    const scanId = scan.scan_id;
    const timer = setInterval(() => {
      talentPoolApi.scanDetail(scanId).then(r => {
        setScan(current => current?.scan_id === scanId ? r.data : current);
        if (!scanIsActive(r.data.status)) talentPoolApi.scans(positionId).then(l => setScans(l.data.items)).catch(() => undefined);
      }).catch(() => undefined);
    }, 3000);
    return () => clearInterval(timer);
  }, [active, scan?.scan_id, positionId]);  // eslint-disable-line react-hooks/exhaustive-deps

  const runScan = async () => {
    setBusy(true); setError('');
    try {
      const created = (await talentPoolApi.scan(positionId)).data;
      setScans((await talentPoolApi.scans(positionId)).data.items);
      await loadScan(created.scan_id);
    } catch (err: any) { setError(serverError(err, locale, t('Không thể quét Talent Pool'))); }
    finally { setBusy(false); }
  };

  return <Box>
    <Typography variant="h4" sx={{ mb: 1 }}>{t('Talent Pool')}</Typography>
    <Alert severity="info" sx={{ mb: 3 }}>
      {t('Chỉ gồm hồ sơ HR đã đưa vào pool, ứng viên đã đồng ý cho dùng ở vị trí khác và chưa rút, còn trong hạn 5 năm và không chờ xóa. Hệ thống chỉ gợi ý xếp hạng; HR quyết định liên hệ.')}
    </Alert>

    <Card sx={{ mb: 3 }}><CardContent>
      <Typography variant="h6" sx={{ mb: 2 }}>{t('Quét Talent Pool cho một vị trí')}</Typography>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField select size="small" label={t('Vị trí đang mở')} value={positionId} onChange={e => setPositionId(e.target.value)} sx={{ minWidth: 320 }}>
          {positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.title} · {p.position_code}</MenuItem>)}
        </TextField>
        <Button variant="contained" disabled={!positionId || busy || active} onClick={runScan}>
          {busy || active ? t('Đang quét…') : t('Quét Talent Pool')}
        </Button>
        {scans.length > 1 && (
          <TextField select size="small" label={t('Lượt quét')} value={scan?.scan_id || ''} onChange={e => loadScan(e.target.value)} sx={{ minWidth: 220 }}>
            {scans.map(s => <MenuItem key={s.scan_id} value={s.scan_id}>{new Date(s.created_at).toLocaleString(locale === 'en' ? 'en-GB' : 'vi-VN')}</MenuItem>)}
          </TextField>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
        {t('Chấm bằng luật trên tiêu chí đã duyệt của vị trí, không gửi CV cho AI. Tiêu chí luật không xác định được để “Chưa rõ”.')}
      </Typography>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {(busy || active) && <CircularProgress size={24} sx={{ mt: 2 }} />}
      {scan?.status === 'FAILED' && <Alert severity="error" sx={{ mt: 2 }}>
        {t('Lượt quét thất bại')}{scan.error_message ? `: ${scan.error_message}` : ''}
      </Alert>}
      {active && <Alert severity="info" sx={{ mt: 2 }}>{t('Đang quét ở nền; kết quả sẽ hiện khi hoàn tất.')}</Alert>}
      {scan && scan.status === 'COMPLETED' && <Box sx={{ mt: 2 }}>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
          <Chip label={t('Đủ điều kiện: {0}', scan.eligible_count)} />
          <Chip label={t('Đã chấm: {0}', scan.scored_count)} />
          {scan.failed_count > 0 && <Chip color="warning" label={t('Lỗi: {0}', scan.failed_count)} />}
          {Object.entries(scan.skipped_counts || {}).map(([k, v]) => <Chip key={k} variant="outlined" label={`${t(SKIP_REASONS[k] || k)}: ${v}`} />)}
        </Box>
        {scan.results.length === 0
          ? <Typography color="text.secondary">{t('Không có hồ sơ nào trong pool đủ điều kiện cho vị trí này.')}</Typography>
          : <Table size="small">
            <TableHead><TableRow>
              <TableCell>#</TableCell><TableCell>{t('Hồ sơ')}</TableCell><TableCell>{t('Điểm')}</TableCell>
              <TableCell>{t('Độ phủ bằng chứng')}</TableCell><TableCell>{t('Tiêu chí chưa rõ')}</TableCell>
              <TableCell>{t('Lưu đến')}</TableCell><TableCell>{t('Quyết định của HR')}</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {scan.results.map(r => <ResultRow key={r.application_id} result={r} scanId={scan.scan_id} onDecided={() => loadScan(scan.scan_id)} />)}
            </TableBody>
          </Table>}
      </Box>}
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
