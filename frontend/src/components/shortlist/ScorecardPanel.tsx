'use client';

import * as React from 'react';

import { useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Divider, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import ActionFeedback from '@/components/common/ActionFeedback';
import { useI18n } from '@/i18n/I18nProvider';
import { scorecardsApi } from '@/lib/api';
import { scorecardIsComplete } from '@/lib/phase2Workflow';
import { draftsStorable, purgeShareDrafts, readDraft, removeDraft, scorecardDraftKey, writeDraft } from '@/lib/localDrafts';

type Criterion = { criterion_id: string; name: string; description: string; rating: number | null; insufficient_evidence: boolean; comment: string | null };
type Card = { scorecard_id: string; application_id: string; criteria_version_id: string | null; assessment_id: string | null; status: string; revision: number; due_at: string; overdue: boolean; waiting_for_assessment: boolean; can_edit: boolean; can_reopen: boolean; can_change_due: boolean; can_view_history: boolean; overall_recommendation: string | null; strengths: string | null; concerns: string | null; criteria: Criterion[] };
type Candidate = { application_id: string; candidate_name?: string; display_name?: string };

/**
 * Nguồn scorecard. Hai đường tồn tại song song và **khác nhau ở một chỗ duy
 * nhất**: gọi API nào để lấy danh sách.
 *
 * - `{ kind: 'share', shareId }` — đường shortlist cũ: HM nhận share rồi chấm.
 * - `{ kind: 'interview', interviewId }` — buổi phỏng vấn: người có tên trong
 *   buổi chấm, không đi qua share.
 *
 * Gộp thành một tham số thay vì hai prop rời (`shareId?`, `interviewId?`) để
 * không bao giờ có trạng thái "cả hai" hoặc "không cái nào" — kiểu sai đó bắt
 * buộc mọi chỗ dùng phải kiểm tra null, và chỗ nào quên là một lỗi runtime.
 */
export type ScorecardSource = { kind: 'share'; shareId: string } | { kind: 'interview'; interviewId: string };

/** Khoá gốc cho nháp và cho việc xoá nháp khi mất quyền. */
function sourceKey(source: ScorecardSource): string {
  return source.kind === 'share' ? source.shareId : `interview:${source.interviewId}`;
}

export default function ScorecardPanel({ source, candidates, selectedApplicationId, onAccessLost, onDirtyChange, onProgress }: { source: ScorecardSource; candidates: Candidate[]; selectedApplicationId?: string; onAccessLost?: () => void; onDirtyChange?: (dirty: boolean) => void; onProgress?: (completed: Record<string, number>) => void }) {
  // `shareId` cũ đổi tên thành `draftScope`: nó không còn là share trong đường
  // buổi phỏng vấn, và giữ tên cũ sẽ khiến người đọc sau tưởng vẫn phải có share.
  const draftScope = sourceKey(source);
  const { t, dateLocale } = useI18n();
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [dates, setDates] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<Record<string, Array<{actor_user_id: string; reason: string; created_at: string}>>>({});
  // Drafts are restored only for the same scorecard revision they were typed
  // against. If the server moved on (another session saved, HR reopened, a new
  // assessment was shared) the stale draft is dropped rather than replayed.
  const [restored, setRestored] = useState<Record<string, number>>({});
  const [draftNotice, setDraftNotice] = useState('');
  const [storageBlocked, setStorageBlocked] = useState(false);
  useEffect(() => {
    let live = true;
    setLoading(true); setCards([]); setDirty({}); setHistory({}); setError(''); setRestored({}); setDraftNotice('');
    const load = source.kind === 'share'
      ? () => scorecardsApi.forShare(source.shareId)
      : () => scorecardsApi.forInterview(source.interviewId);
    load().then(res => {
      if (!live) return;
      const restoredAt: Record<string, number> = {};
      const withDrafts = (res.data as Card[]).map(card => {
        const draft = readDraft<{ revision: number; card: Partial<Card> }>(scorecardDraftKey(draftScope, card.scorecard_id));
        if (!draft) return card;
        if (draft.revision !== card.revision || !card.can_edit) {
          removeDraft(scorecardDraftKey(draftScope, card.scorecard_id));
          return card;
        }
        restoredAt[card.scorecard_id] = draft.revision;
        const merged = { ...card, ...draft.card, scorecard_id: card.scorecard_id, application_id: card.application_id, revision: card.revision } as Card;
        // A draft that no longer differs from the server copy is not worth restoring.
        if (JSON.stringify(merged) === JSON.stringify(card)) { removeDraft(scorecardDraftKey(draftScope, card.scorecard_id)); return card; }
        return merged;
      });
      setCards(withDrafts);
      setRestored(restoredAt);
      setDirty(Object.fromEntries(Object.keys(restoredAt).map(id => [id, true])));
      if (Object.keys(restoredAt).length) setDraftNotice(t('Đã khôi phục nháp scorecard chưa gửi trên trình duyệt này. Kiểm tra lại rồi lưu hoặc bỏ nháp.'));
      setStorageBlocked(!draftsStorable());
    })
      .catch((err: any) => {
        if (!live) return;
        if ([403, 404].includes(err.response?.status)) { purgeShareDrafts(draftScope); onAccessLost?.(); }
        else setError(t('Không thể tải scorecard.'));
      })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
      // eslint-disable-next-line react-hooks/exhaustive-deps -- `source` là object mới mỗi render
  }, [sourceKey(source), t, onAccessLost]);

  const persistTimer = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const update = (id: string, patch: Partial<Card>) => {
    setDirty(current => ({ ...current, [id]: true }));
    setCards(current => {
      const next = current.map(c => c.scorecard_id === id ? { ...c, ...patch } : c);
      const card = next.find(c => c.scorecard_id === id);
      if (card) {
        // Debounce so typing does not hit localStorage on every keystroke.
        if (persistTimer.current[id]) clearTimeout(persistTimer.current[id]);
        persistTimer.current[id] = setTimeout(() => {
          const ok = writeDraft(scorecardDraftKey(draftScope, id), { revision: card.revision, card: {
            overall_recommendation: card.overall_recommendation, strengths: card.strengths,
            concerns: card.concerns, criteria: card.criteria,
          } });
          if (!ok) setStorageBlocked(true);
          delete persistTimer.current[id];
        }, 400);
      }
      return next;
    });
  };
  useEffect(() => () => { Object.values(persistTimer.current).forEach(clearTimeout); }, []);
  const clearTimer = (id: string) => {
    // A pending debounce must not resurrect a draft we are about to drop.
    if (persistTimer.current[id]) { clearTimeout(persistTimer.current[id]); delete persistTimer.current[id]; }
  };
  const [saved, setSaved] = React.useState<string | null>(null);
  const run = async (operation: () => Promise<{ data: Card }>, successMessage?: string) => {
    try {
      setBusy(true); setError('');
      setSaved(null);
      const result = await operation();
      setCards(current => current.map(c => c.scorecard_id === result.data.scorecard_id ? result.data : c));
      setDirty(current => ({ ...current, [result.data.scorecard_id]: false }));
      // The server accepted the work, so the local copy is no longer needed.
      clearTimer(result.data.scorecard_id);
      removeDraft(scorecardDraftKey(draftScope, result.data.scorecard_id));
      setRestored(current => { const next = { ...current }; delete next[result.data.scorecard_id]; return next; });
      setDraftNotice('');
      // Previously a successful save was silent: the spinner stopped and nothing
      // else changed, so HR could not tell whether the scorecard was stored or
      // the click was lost. Say it, out loud, including for screen readers.
      if (successMessage) setSaved(successMessage);
    } catch (err: any) { if ([403, 404].includes(err.response?.status)) onAccessLost?.(); else setError(err.response?.data?.detail || t('Không thể cập nhật scorecard.')); }
    finally { setBusy(false); }
  };
  const discardDraft = async (card: Card) => {
    clearTimer(card.scorecard_id);
    removeDraft(scorecardDraftKey(draftScope, card.scorecard_id));
    setRestored(current => { const next = { ...current }; delete next[card.scorecard_id]; return next; });
    setDraftNotice('');
    // Refetch this share so the screen shows the saved server values again
    // without throwing away edits pending on other scorecards.
    try {
      setBusy(true);
      const res = source.kind === 'share' ? await scorecardsApi.forShare(source.shareId) : await scorecardsApi.forInterview(source.interviewId);
      const fresh = (res.data as Card[]).find(c => c.scorecard_id === card.scorecard_id);
      if (fresh) setCards(current => current.map(c => c.scorecard_id === card.scorecard_id ? fresh : c));
      setDirty(current => ({ ...current, [card.scorecard_id]: false }));
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải lại scorecard.')); }
    finally { setBusy(false); }
  };
  const loadHistory = async (id: string) => {
    try { setBusy(true); setError(''); const result = await scorecardsApi.reopenHistory(id); setHistory(current => ({ ...current, [id]: result.data })); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải lịch sử mở lại.')); }
    finally { setBusy(false); }
  };
  useEffect(() => { onDirtyChange?.(Object.values(dirty).some(Boolean)); }, [dirty, onDirtyChange]);
  // Compact, non-ranking progress so a reviewer scanning the candidate list can
  // see which scorecards still need work without opening each one.
  useEffect(() => {
    const completed: Record<string, number> = {};
    for (const card of cards) {
      const decided = card.criteria.filter(criterion => criterion.insufficient_evidence || (criterion.rating != null && criterion.rating >= 1)).length;
      completed[card.application_id] = card.criteria.length ? Math.round((decided / card.criteria.length) * 100) : (card.overall_recommendation ? 100 : 0);
    }
    onProgress?.(completed);
  }, [cards, onProgress]);
  const save = (card: Card) => run(() => scorecardsApi.save(card.scorecard_id, {
    expected_revision: card.revision, overall_recommendation: card.overall_recommendation,
    strengths: card.strengths, concerns: card.concerns,
    ratings: card.criteria.map(c => ({ criterion_id: c.criterion_id, rating: c.rating, insufficient_evidence: c.insufficient_evidence, comment: c.comment })),
  }), 'Đã lưu nháp scorecard.');
  return <Box sx={{ mb: 3 }}>
    <Typography variant="subtitle1" fontWeight={700}>{t('Scorecard đánh giá')}</Typography>
    {error && <Alert severity="error" sx={{ my: 1 }}>{t(error)}</Alert>}
    <ActionFeedback success={saved} onSuccessClose={() => setSaved(null)} />
    {draftNotice && <Alert severity="info" sx={{ my: 1 }} onClose={() => setDraftNotice('')}>{t(draftNotice)}</Alert>}
    {storageBlocked && <Alert severity="warning" sx={{ my: 1 }}>{t('Trình duyệt không cho lưu nháp trên máy này. Nháp scorecard chỉ tồn tại đến khi rời trang hoặc tải lại.')}</Alert>}
    {loading && <CircularProgress size={22} />}
    {!loading && !error && !cards.length && <Typography variant="body2">{t(source.kind === 'share' ? 'Share cũ không có scorecard.' : 'Buổi phỏng vấn chưa có phiếu chấm điểm. Người phụ trách cần bấm "Tạo phiếu chấm điểm" sau khi buổi đã diễn ra.')}</Typography>}
    {cards.map(card => <Paper key={card.scorecard_id} variant="outlined" sx={{ p: 2, my: 2, display: selectedApplicationId && card.application_id !== selectedApplicationId ? 'none' : undefined }}>
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
          {card.can_edit && <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}><Button disabled={busy} onClick={() => save(card)}>{t('Lưu nháp scorecard')}</Button>
            {typeof restored[card.scorecard_id] === 'number' && <Button color="inherit" disabled={busy} onClick={() => discardDraft(card)}>{t('Bỏ nháp đã khôi phục')}</Button>}<Button disabled={busy || !!dirty[card.scorecard_id] || !scorecardIsComplete(card.overall_recommendation, card.criteria)} variant="contained" onClick={() => run(() => scorecardsApi.submit(card.scorecard_id, card.revision), 'Đã nộp scorecard.')}>{t('Nộp bản đã lưu')}</Button></Stack>}
          {card.can_edit && <Typography variant="caption">{t('Lưu thay đổi trước khi nộp. Cần đánh giá mọi tiêu chí và chọn khuyến nghị.')}</Typography>}
        </>}
        {card.can_reopen && <><TextField fullWidth helperText={t('Lý do chỉ hiển thị cho HR có quyền.')} label={t('Lý do mở lại')} value={reasons[card.scorecard_id] || ''} onChange={e => setReasons({ ...reasons, [card.scorecard_id]: e.target.value })} /><Button disabled={busy || !reasons[card.scorecard_id]?.trim()} onClick={() => run(() => scorecardsApi.reopen(card.scorecard_id, card.revision, reasons[card.scorecard_id]))}>{t('Mở lại scorecard')}</Button></>}
        {card.can_view_history && <><Button disabled={busy} onClick={() => loadHistory(card.scorecard_id)}>{t('Xem lịch sử mở lại')}</Button>{history[card.scorecard_id] && (history[card.scorecard_id].length ? history[card.scorecard_id].map((event, i) => <Typography variant="body2" key={i}>{new Date(event.created_at).toLocaleString(dateLocale)} · {event.actor_user_id}: {event.reason}</Typography>) : <Typography variant="body2">{t('Chưa có lịch sử mở lại.')}</Typography>)}</>}
        {card.can_change_due && <><Divider /><TextField type="datetime-local" label={t('Đổi hạn phản hồi')} InputLabelProps={{ shrink: true }} value={dates[card.scorecard_id] || ''} onChange={e => setDates({ ...dates, [card.scorecard_id]: e.target.value })} /><Button disabled={busy || !!dirty[card.scorecard_id] || !dates[card.scorecard_id]} onClick={() => run(() => scorecardsApi.setDueDate(card.scorecard_id, card.revision, new Date(dates[card.scorecard_id]).toISOString()))}>{t('Cập nhật hạn')}</Button></>}
      </Stack>
    </Paper>)}
  </Box>;
}
