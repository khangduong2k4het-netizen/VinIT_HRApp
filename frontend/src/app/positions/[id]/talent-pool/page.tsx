'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, CardContent, Chip, CircularProgress,
  LinearProgress, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { positionsApi, talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { REVIEW_LABELS } from '@/lib/reviewLabels';
import { MATCHING_STATUS_LABELS, POOL_REASONS, SCAN_STATUS_LABELS, type Scan, type ScanResult } from '@/lib/talentPool';

const percent = (value: number | null) => (value == null ? '—' : `${Math.round(value * 100)}%`);

/** P3-1: scan the Talent Pool against this position's approved criteria and rank the matches. */
export default function PositionTalentPoolPage() {
  const { t, dateLocale } = useI18n();
  const params = useParams();
  const positionId = params.id as string;
  const [title, setTitle] = useState('');
  const [scan, setScan] = useState<Scan | null>(null);
  const [results, setResults] = useState<ScanResult[]>([]);
  const [hidden, setHidden] = useState(0);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await talentPoolApi.latestScan(positionId);
      setScan(res.data.scan); setResults(res.data.results || []); setHidden(res.data.hidden_count || 0); setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể tải kết quả quét Talent Pool'));
    } finally { setLoading(false); }
  }, [positionId, t]);

  useEffect(() => {
    load();
    positionsApi.getById(positionId).then(res => setTitle(`${res.data.position_code} · ${res.data.title}`)).catch(() => {});
  }, [load, positionId]);

  // Poll while the worker is scanning.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (scan && (scan.status === 'PENDING' || scan.status === 'PROCESSING')) timer.current = setTimeout(load, 3000);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [scan, load]);

  const start = async () => {
    if (starting) return;
    setStarting(true); setError('');
    try { await talentPoolApi.startScan(positionId); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể bắt đầu quét Talent Pool')); }
    finally { setStarting(false); }
  };

  const running = scan?.status === 'PENDING' || scan?.status === 'PROCESSING';
  return (
    <Box>
      <Button component={Link} href={`/positions/${positionId}`} startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>{t('Quay lại vị trí')}</Button>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <Box>
          <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>{t('Quét Talent Pool')}</Typography>
          <Typography variant="body2" color="text.secondary">{title}</Typography>
        </Box>
        <Button variant="contained" color="secondary" onClick={start} disabled={starting || running}>
          {starting ? <CircularProgress size={18} color="inherit" /> : scan ? t('Quét lại') : t('Bắt đầu quét')}
        </Button>
      </Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        {t('Hệ thống chấm các hồ sơ trong Talent Pool theo bộ tiêu chí đã duyệt của vị trí này, giống cách chấm hồ sơ nộp trực tiếp. Chỉ quét hồ sơ ứng viên đã đồng ý cho dùng lại, còn thời hạn và không chờ xóa. Kết quả để HR chủ động liên hệ; hồ sơ không tự được thêm vào vị trí.')}
      </Alert>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {loading ? <CircularProgress /> : !scan ? (
        <Typography color="text.secondary">{t('Chưa quét Talent Pool cho vị trí này.')}</Typography>
      ) : (
        <>
          <Card sx={{ mb: 2 }}><CardContent>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <Chip size="small" color={scan.status === 'COMPLETED' ? 'success' : scan.status === 'FAILED' ? 'error' : 'warning'}
                label={t(SCAN_STATUS_LABELS[scan.status] || scan.status)} />
              <Typography variant="body2">
                {t('{0} hồ sơ trong pool phù hợp điều kiện · đã chấm {1} · lỗi {2}', scan.candidate_count, scan.scored_count, scan.failed_count)}
              </Typography>
              <Typography variant="caption" color="text.secondary">{new Date(scan.created_at).toLocaleString(dateLocale)}</Typography>
            </Box>
            {running && <LinearProgress sx={{ mt: 1.5 }} />}
            {scan.error_message && <Alert severity="error" sx={{ mt: 1.5 }}>{t(scan.error_message)}</Alert>}
            {hidden > 0 && (
              <Alert severity="warning" sx={{ mt: 1.5 }}>
                {t('{0} hồ sơ đã bị ẩn vì ứng viên rút đồng ý, hết thời hạn hoặc bị gỡ khỏi Talent Pool sau lần quét.', hidden)}
              </Alert>
            )}
          </CardContent></Card>
          {scan.status === 'COMPLETED' && results.length === 0 && (
            <Typography color="text.secondary">{t('Không có hồ sơ nào trong Talent Pool để đề xuất cho vị trí này.')}</Typography>
          )}
          {results.map(result => {
            const meta = MATCHING_STATUS_LABELS[result.matching_status || 'NOT_ASSESSED'] || MATCHING_STATUS_LABELS.NOT_ASSESSED;
            return (
              <Accordion key={result.application_id} disableGutters sx={{ mb: 1, border: '1px solid #E4E7EC', '&:before': { display: 'none' } }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', width: '100%' }}>
                    <Typography sx={{ fontWeight: 700, minWidth: 28 }}>{result.rank_number ? `#${result.rank_number}` : '—'}</Typography>
                    <Box sx={{ flex: 1, minWidth: 200 }}>
                      <Typography sx={{ fontWeight: 600 }}>{result.candidate_name || t('Chưa trích xuất tên')}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {t('Từ {0} · {1}', result.source_position_code, result.source_position_title)}
                        {result.reason_code ? ` · ${t(POOL_REASONS[result.reason_code] || result.reason_code)}` : ''}
                      </Typography>
                    </Box>
                    {result.status === 'FAILED' ? <Chip size="small" color="error" label={t('Không chấm được')} /> : (
                      <>
                        <Chip size="small" color={meta.color} label={t(meta.label)} />
                        <Typography variant="body2">{t('Điểm')}: {percent(result.matching_score != null ? result.matching_score / 100 : null)}</Typography>
                        <Typography variant="body2">{t('Độ phủ')}: {percent(result.evidence_coverage)}</Typography>
                      </>
                    )}
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    {t('Liên hệ')}: {result.email || '—'}{result.phone ? ` · ${result.phone}` : ''}
                  </Typography>
                  {result.criteria.map(criterion => (
                    <Box key={criterion.criterion_id} sx={{ py: 0.75, borderTop: '1px solid #EDF1F5' }}>
                      <Typography variant="body2">
                        <b>{criterion.name}</b> · {criterion.category === 'MUST_HAVE' ? t('Bắt buộc') : t('Ưu tiên')} ·{' '}
                        {t(REVIEW_LABELS[criterion.outcome || 'UNCLEAR'] || criterion.outcome || '')}
                      </Typography>
                      {criterion.quote && <Typography variant="caption" color="text.secondary">“{criterion.quote}”</Typography>}
                    </Box>
                  ))}
                </AccordionDetails>
              </Accordion>
            );
          })}
        </>
      )}
    </Box>
  );
}
