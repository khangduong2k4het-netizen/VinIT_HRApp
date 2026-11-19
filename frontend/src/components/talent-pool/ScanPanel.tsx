'use client';

// P3-1: scan the Talent Pool against one open position (async worker job, polled) and rank the matches.
// Rules-only scoring: no CV text is sent to an AI provider. No names or contact data are shown.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, ButtonGroup, Chip, CircularProgress, Collapse, MenuItem, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import Link from 'next/link';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { DECISIONS, OUTCOMES, SKIP_REASONS, poolRef, scoreText,
  scanIsActive, type ScanDetail, type ScanResult, type ScanSummary } from '@/lib/talentPool';

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

export default function ScanPanel({ positionId }: { positionId: string }) {
  const { t, locale } = useI18n();
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

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

  return <>
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
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
  </>;
}
