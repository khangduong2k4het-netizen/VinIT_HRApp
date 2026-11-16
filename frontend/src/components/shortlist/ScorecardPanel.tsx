'use client';

import { useEffect, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Divider, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { scorecardsApi } from '@/lib/api';
import { scorecardIsComplete } from '@/lib/phase2Workflow';

type Criterion = { criterion_id: string; name: string; description: string; rating: number | null; insufficient_evidence: boolean; comment: string | null };
type Card = { scorecard_id: string; application_id: string; criteria_version_id: string | null; assessment_id: string | null; status: string; revision: number; due_at: string; overdue: boolean; waiting_for_assessment: boolean; can_edit: boolean; can_reopen: boolean; can_change_due: boolean; can_view_history: boolean; overall_recommendation: string | null; strengths: string | null; concerns: string | null; criteria: Criterion[] };
type Candidate = { application_id: string; candidate_name?: string; display_name?: string };

export default function ScorecardPanel({ shareId, candidates }: { shareId: string; candidates: Candidate[] }) {
  const { t, dateLocale } = useI18n();
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [dates, setDates] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Record<string, Array<{actor_user_id: string; reason: string; created_at: string}>>>({});
  useEffect(() => {
    let live = true;
    setLoading(true); setCards([]); setDirty({}); setHistory({}); setError('');
    scorecardsApi.forShare(shareId).then(res => { if (live) setCards(res.data); })
      .catch(() => { if (live) setError(t('Không thể tải scorecard.')); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [shareId, t]);

  const update = (id: string, patch: Partial<Card>) => {
    setDirty(current => ({ ...current, [id]: true }));
    setCards(current => current.map(c => c.scorecard_id === id ? { ...c, ...patch } : c));
  };
  const run = async (operation: () => Promise<{ data: Card }>) => {
    try {
      setBusy(true); setError('');
      const result = await operation();
      setCards(current => current.map(c => c.scorecard_id === result.data.scorecard_id ? result.data : c));
      setDirty(current => ({ ...current, [result.data.scorecard_id]: false }));
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể cập nhật scorecard.')); }
    finally { setBusy(false); }
  };
  const loadHistory = async (id: string) => {
    try { setBusy(true); setError(''); const result = await scorecardsApi.reopenHistory(id); setHistory(current => ({ ...current, [id]: result.data })); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải lịch sử mở lại.')); }
    finally { setBusy(false); }
  };
  const save = (card: Card) => run(() => scorecardsApi.save(card.scorecard_id, {
    expected_revision: card.revision, overall_recommendation: card.overall_recommendation,
    strengths: card.strengths, concerns: card.concerns,
    ratings: card.criteria.map(c => ({ criterion_id: c.criterion_id, rating: c.rating, insufficient_evidence: c.insufficient_evidence, comment: c.comment })),
  }));
  return <Box sx={{ mb: 3 }}>
    <Typography variant="subtitle1" fontWeight={700}>{t('Scorecard đánh giá')}</Typography>
    {error && <Alert severity="error" sx={{ my: 1 }}>{t(error)}</Alert>}
    {loading && <CircularProgress size={22} />}
    {!loading && !cards.length && <Typography variant="body2">{t('Share cũ không có scorecard.')}</Typography>}
    {cards.map(card => <Paper key={card.scorecard_id} variant="outlined" sx={{ p: 2, my: 2 }}>
      <Stack spacing={1.5}>
        <Typography fontWeight={700}>{candidates.find(c => c.application_id === card.application_id)?.candidate_name || candidates.find(c => c.application_id === card.application_id)?.display_name || t('Ứng viên')}</Typography>
        <Typography variant="body2">{t('Trạng thái scorecard')}: {card.status === 'SUBMITTED' ? t('Đã nộp') : card.status === 'IN_PROGRESS' ? t('Đang thực hiện') : t('Chưa bắt đầu')} · {t('Hạn phản hồi')}: {new Date(card.due_at).toLocaleString(dateLocale)} {card.overdue ? `— ${t('Quá hạn')}` : ''}</Typography>
        {card.waiting_for_assessment ? <Alert severity="warning">{t('Chưa có assessment snapshot; HR cần chia sẻ lại sau khi đánh giá.')}</Alert> : <>
          <Typography variant="caption">Assessment: {card.assessment_id} · Criteria: {card.criteria_version_id}</Typography>
          {card.criteria.map(criterion => <Box key={criterion.criterion_id}>
            <Typography fontWeight={600}>{criterion.name}</Typography><Typography variant="body2">{criterion.description}</Typography>
            <TextField select size="small" fullWidth label={t('Đánh giá')} sx={{ mt: 1 }} disabled={!card.can_edit || busy}
              value={criterion.insufficient_evidence ? 'insufficient' : criterion.rating?.toString() || ''}
              onChange={event => update(card.scorecard_id, { criteria: card.criteria.map(c => c.criterion_id !== criterion.criterion_id ? c : { ...c, rating: event.target.value && event.target.value !== 'insufficient' ? Number(event.target.value) : null, insufficient_evidence: event.target.value === 'insufficient' }) })}>
              <MenuItem value="">{t('Chưa đánh giá')}</MenuItem>{[1,2,3,4,5].map(n => <MenuItem key={n} value={String(n)}>{n}</MenuItem>)}<MenuItem value="insufficient">{t('Thiếu bằng chứng')}</MenuItem>
            </TextField>
            <TextField fullWidth size="small" sx={{ mt: 1 }} label={t('Nhận xét tiêu chí')} value={criterion.comment || ''} disabled={!card.can_edit || busy}
              onChange={event => update(card.scorecard_id, { criteria: card.criteria.map(c => c.criterion_id !== criterion.criterion_id ? c : { ...c, comment: event.target.value }) })} />
          </Box>)}
          <TextField select fullWidth label={t('Khuyến nghị tổng thể')} value={card.overall_recommendation || ''} disabled={!card.can_edit || busy} onChange={e => update(card.scorecard_id, { overall_recommendation: e.target.value || null })}>
            <MenuItem value="">{t('Chưa chọn')}</MenuItem>
            <MenuItem value="STRONGLY_RECOMMEND">{t('Rất nên')}</MenuItem>
            <MenuItem value="RECOMMEND">{t('Nên')}</MenuItem>
            <MenuItem value="CONSIDER">{t('Cân nhắc')}</MenuItem>
            <MenuItem value="NOT_RECOMMEND">{t('Không nên')}</MenuItem>
          </TextField>
          <TextField fullWidth multiline label={t('Điểm mạnh')} value={card.strengths || ''} disabled={!card.can_edit || busy} onChange={e => update(card.scorecard_id, { strengths: e.target.value })} />
          <TextField fullWidth multiline label={t('Điểm cần xem xét')} value={card.concerns || ''} disabled={!card.can_edit || busy} onChange={e => update(card.scorecard_id, { concerns: e.target.value })} />
          {card.can_edit && <Stack direction="row" spacing={1}><Button disabled={busy} onClick={() => save(card)}>{t('Lưu nháp scorecard')}</Button><Button disabled={busy || !!dirty[card.scorecard_id] || !scorecardIsComplete(card.overall_recommendation, card.criteria)} variant="contained" onClick={() => run(() => scorecardsApi.submit(card.scorecard_id, card.revision))}>{t('Nộp bản đã lưu')}</Button></Stack>}
          {card.can_edit && <Typography variant="caption">{t('Lưu thay đổi trước khi nộp. Cần đánh giá mọi tiêu chí và chọn khuyến nghị.')}</Typography>}
        </>}
        {card.can_reopen && <><TextField fullWidth helperText={t('Lý do chỉ hiển thị cho HR có quyền.')} label={t('Lý do mở lại')} value={reasons[card.scorecard_id] || ''} onChange={e => setReasons({ ...reasons, [card.scorecard_id]: e.target.value })} /><Button disabled={busy || !reasons[card.scorecard_id]?.trim()} onClick={() => run(() => scorecardsApi.reopen(card.scorecard_id, card.revision, reasons[card.scorecard_id]))}>{t('Mở lại scorecard')}</Button></>}
        {card.can_view_history && <><Button disabled={busy} onClick={() => loadHistory(card.scorecard_id)}>{t('Xem lịch sử mở lại')}</Button>{history[card.scorecard_id] && (history[card.scorecard_id].length ? history[card.scorecard_id].map((event, i) => <Typography variant="body2" key={i}>{new Date(event.created_at).toLocaleString(dateLocale)} · {event.actor_user_id}: {event.reason}</Typography>) : <Typography variant="body2">{t('Chưa có lịch sử mở lại.')}</Typography>)}</>}
        {card.can_change_due && <><Divider /><TextField type="datetime-local" label={t('Đổi hạn phản hồi')} InputLabelProps={{ shrink: true }} value={dates[card.scorecard_id] || ''} onChange={e => setDates({ ...dates, [card.scorecard_id]: e.target.value })} /><Button disabled={busy || !!dirty[card.scorecard_id] || !dates[card.scorecard_id]} onClick={() => run(() => scorecardsApi.setDueDate(card.scorecard_id, card.revision, new Date(dates[card.scorecard_id]).toISOString()))}>{t('Cập nhật hạn')}</Button></>}
      </Stack>
    </Paper>)}
  </Box>;
}
