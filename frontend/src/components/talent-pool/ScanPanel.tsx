'use client';

// P3-1: scan the Talent Pool against one open position (async worker job, polled) and rank the matches.
// Rules-only scoring: no CV text is sent to an AI provider. Contact data is revealed only after HR marks CONTACT (audited).
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, ButtonGroup, Chip, CircularProgress, Collapse, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import Link from 'next/link';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { buildMailtoHref, DECISIONS, OUTCOMES, SKIP_REASONS, poolRef, scoreText, scanIsActive,
  type PoolContact, type ScanDetail, type ScanResult, type ScanSummary } from '@/lib/talentPool';

function serverError(err: any, locale: 'vi' | 'en', fallback: string): string {
  const detail = err?.response?.data?.detail;
  return typeof detail === 'string' ? localizeServerMessage(detail, locale) : fallback;
}

type DecisionFilter = 'ALL' | 'UNDECIDED' | 'CONTACT' | 'LATER' | 'SKIP';

function ResultRow({
  result,
  scanId,
  onDecided,
  onOpenContact,
}: {
  result: ScanResult;
  scanId: string;
  onDecided: () => void;
  onOpenContact: (applicationId: string) => void;
}) {
  const { t, locale } = useI18n();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const decide = async (decision: 'CONTACT' | 'SKIP' | 'LATER') => {
    setBusy(true); setError('');
    try {
      await talentPoolApi.decide(scanId, result.application_id, decision);
      onDecided();
      if (decision === 'CONTACT') onOpenContact(result.application_id);
    } catch (err: any) {
      setError(serverError(err, locale, t('Không thể lưu quyết định')));
    } finally {
      setBusy(false);
    }
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
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <ButtonGroup size="small" disabled={busy}>
            {(['CONTACT', 'LATER', 'SKIP'] as const).map(d => (
              <Button key={d} variant={result.hr_decision === d ? 'contained' : 'outlined'} onClick={() => decide(d)}>{t(DECISIONS[d])}</Button>
            ))}
          </ButtonGroup>
          {result.hr_decision === 'CONTACT' && (
            <Button size="small" variant="text" onClick={() => onOpenContact(result.application_id)}>
              {t('Xem liên hệ & mẫu email')}
            </Button>
          )}
        </Stack>
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
  const [filter, setFilter] = useState<DecisionFilter>('ALL');

  const [contactOpen, setContactOpen] = useState(false);
  const [contactLoading, setContactLoading] = useState(false);
  const [contactError, setContactError] = useState('');
  const [contact, setContact] = useState<PoolContact | null>(null);
  const [draftSubject, setDraftSubject] = useState('');
  const [draftBody, setDraftBody] = useState('');
  const [copiedEmail, setCopiedEmail] = useState(false);

  const loadScan = useCallback(async (scanId: string) => {
    try { setScan((await talentPoolApi.scanDetail(scanId)).data); }
    catch (err: any) { setError(serverError(err, locale, t('Không thể tải kết quả quét'))); }
  }, [locale, t]);

  useEffect(() => {
    setScan(null); setScans([]); setError(''); setFilter('ALL');
    if (!positionId) return;
    talentPoolApi.scans(positionId).then(r => {
      setScans(r.data.items);
      if (r.data.items.length) loadScan(r.data.items[0].scan_id);
    }).catch(() => setScans([]));
  }, [positionId, loadScan]);

  // The worker scores the pool in the background: poll the lightweight scan list
  // until the active scan leaves PENDING/PROCESSING, then fetch full results once.
  const active = scanIsActive(scan?.status);
  useEffect(() => {
    if (!active || !scan) return;
    const scanId = scan.scan_id;
    const timer = setInterval(() => {
      talentPoolApi.scans(positionId).then(listRes => {
        const items: ScanSummary[] = listRes.data.items || [];
        setScans(items);
        const match = items.find(item => item.scan_id === scanId);
        if (!match) return;
        if (scanIsActive(match.status)) {
          setScan(current => current?.scan_id === scanId ? { ...current, ...match } : current);
        } else {
          talentPoolApi.scanDetail(scanId)
            .then(detailRes => setScan(current => current?.scan_id === scanId ? detailRes.data : current))
            .catch(() => undefined);
        }
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

  const openContact = async (applicationId: string) => {
    if (!scan) return;
    setContactOpen(true);
    setContactLoading(true);
    setContactError('');
    setContact(null);
    setCopiedEmail(false);
    try {
      const data: PoolContact = (await talentPoolApi.revealContact(scan.scan_id, applicationId)).data;
      setContact(data);
      setDraftSubject(data.email_subject);
      setDraftBody(data.email_body);
    } catch (err: any) {
      setContactError(serverError(err, locale, t('Không thể tải thông tin liên hệ')));
    } finally {
      setContactLoading(false);
    }
  };

  const copyDraft = async () => {
    try {
      await navigator.clipboard.writeText(`${draftSubject}\n\n${draftBody}`);
      setCopiedEmail(true);
      window.setTimeout(() => setCopiedEmail(false), 2000);
    } catch {
      setCopiedEmail(false);
    }
  };

  const visibleResults = (scan?.results || []).filter(r => {
    if (filter === 'ALL') return true;
    if (filter === 'UNDECIDED') return !r.hr_decision;
    return r.hr_decision === filter;
  });

  const filterChips: { value: DecisionFilter; label: string }[] = [
    { value: 'ALL', label: t('Tất cả') },
    { value: 'UNDECIDED', label: t('Chưa quyết định') },
    { value: 'CONTACT', label: t('Liên hệ') },
    { value: 'LATER', label: t('Để sau') },
    { value: 'SKIP', label: t('Bỏ qua') },
  ];

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
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
        <Chip label={t('Đủ điều kiện: {0}', scan.eligible_count)} />
        <Chip label={t('Đã chấm: {0}', scan.scored_count)} />
        {scan.failed_count > 0 && <Chip color="warning" label={t('Lỗi: {0}', scan.failed_count)} />}
        {Object.entries(scan.skipped_counts || {}).map(([k, v]) => <Chip key={k} variant="outlined" label={`${t(SKIP_REASONS[k] || k)}: ${v}`} />)}
      </Box>
      {scan.results.length > 0 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
          {filterChips.map(c => (
            <Chip
              key={c.value}
              size="small"
              label={c.label}
              color={filter === c.value ? 'primary' : 'default'}
              variant={filter === c.value ? 'filled' : 'outlined'}
              onClick={() => setFilter(c.value)}
            />
          ))}
        </Stack>
      )}
      {scan.results.length === 0
        ? <Typography color="text.secondary">{t('Không có hồ sơ nào trong pool đủ điều kiện cho vị trí này.')}</Typography>
        : visibleResults.length === 0
          ? <Typography color="text.secondary">{t('Không có hồ sơ nào khớp bộ lọc hiện tại.')}</Typography>
          : <Table size="small">
            <TableHead><TableRow>
              <TableCell>#</TableCell><TableCell>{t('Hồ sơ')}</TableCell><TableCell>{t('Điểm')}</TableCell>
              <TableCell>{t('Độ phủ bằng chứng')}</TableCell><TableCell>{t('Tiêu chí chưa rõ')}</TableCell>
              <TableCell>{t('Lưu đến')}</TableCell><TableCell>{t('Quyết định của HR')}</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {visibleResults.map(r => (
                <ResultRow key={r.application_id} result={r} scanId={scan.scan_id}
                  onDecided={() => loadScan(scan.scan_id)} onOpenContact={openContact} />
              ))}
            </TableBody>
          </Table>}
    </Box>}

    <Dialog open={contactOpen} onClose={() => setContactOpen(false)} maxWidth="md" fullWidth>
      <DialogTitle>{t('Thông tin liên hệ & gợi ý email')}</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          {t('Hệ thống không tự gửi email và không tự tạo hồ sơ ứng tuyển mới. Lượt xem thông tin liên hệ này đã được ghi nhận vào nhật ký audit.')}
        </Alert>
        {contactLoading && <CircularProgress size={24} />}
        {contactError && <Alert severity="error">{contactError}</Alert>}
        {contact && (
          <Stack spacing={2}>
            <Box sx={{ p: 1.5, bgcolor: '#F8FAFC', borderRadius: 1, border: '1px solid #E2E8F0' }}>
              <Typography variant="body2"><strong>{t('Ứng viên')}:</strong> {contact.display_name || poolRef(contact.application_id)}</Typography>
              <Typography variant="body2"><strong>Email:</strong> {contact.email || '—'}</Typography>
              <Typography variant="body2"><strong>{t('Số điện thoại')}:</strong> {contact.phone || '—'}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t('Từ vị trí')}: {contact.source_position_title} ({contact.source_position_code})
              </Typography>
            </Box>
            <TextField fullWidth size="small" label={t('Tiêu đề email')} value={draftSubject}
              onChange={e => setDraftSubject(e.target.value)} />
            <TextField fullWidth size="small" multiline minRows={8} label={t('Nội dung email xem trước')}
              value={draftBody} onChange={e => setDraftBody(e.target.value)} />
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {contact && (
          <>
            <Button variant="outlined" onClick={copyDraft}>
              {copiedEmail ? t('Đã sao chép email') : t('Sao chép nội dung email')}
            </Button>
            {contact.email && (
              <Button variant="contained" component="a" href={buildMailtoHref(contact.email, draftSubject, draftBody)}>
                {t('Mở trong ứng dụng email')}
              </Button>
            )}
          </>
        )}
        <Button onClick={() => setContactOpen(false)}>{t('Đóng')}</Button>
      </DialogActions>
    </Dialog>
  </>;
}
