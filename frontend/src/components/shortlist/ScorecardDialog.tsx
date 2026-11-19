'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider,
  MenuItem, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { scorecardApi } from '@/lib/api';
import type { Recommendation, Scorecard, ScorecardCriterion } from '@/types';

export const RECOMMENDATION_LABELS: Record<Recommendation, string> = {
  STRONG_YES: 'Rất nên mời phỏng vấn',
  YES: 'Nên mời phỏng vấn',
  NO: 'Chưa nên mời',
  STRONG_NO: 'Không phù hợp',
};

export const SCORECARD_STATUS_LABELS: Record<string, string> = {
  NOT_STARTED: 'Chưa bắt đầu',
  IN_PROGRESS: 'Đang chấm',
  SUBMITTED: 'Đã nộp',
};

type Answer = 'INSUFFICIENT' | '1' | '2' | '3' | '4' | '5' | null;

interface Draft {
  answers: Record<string, { answer: Answer; comment: string }>;
  overall: Recommendation | '';
  strengths: string;
  concerns: string;
}

function toDraft(card: Scorecard): Draft {
  const answers: Draft['answers'] = {};
  for (const c of card.criteria || []) {
    answers[c.criterion_id] = {
      answer: c.evidence_assessment === 'INSUFFICIENT_EVIDENCE' ? 'INSUFFICIENT' : c.rating ? (String(c.rating) as Answer) : null,
      comment: c.comment || '',
    };
  }
  return { answers, overall: card.overall_recommendation || '', strengths: card.strengths || '', concerns: card.concerns || '' };
}

export default function ScorecardDialog({ scorecardId, onClose, onChanged }: {
  scorecardId: string | null; onClose: () => void; onChanged?: () => void;
}) {
  const { t, dateLocale } = useI18n();
  const [card, setCard] = useState<Scorecard | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reopenReason, setReopenReason] = useState('');
  const [reopenOpen, setReopenOpen] = useState(false);

  const apply = (data: Scorecard) => { setCard(data); setDraft(toDraft(data)); };

  const load = useCallback(async (id: string) => {
    try {
      setLoading(true); setError(null); setNotice(null);
      apply((await scorecardApi.get(id)).data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải scorecard"));
    } finally { setLoading(false); }
  }, [t]);

  useEffect(() => {
    setCard(null); setDraft(null); setReopenOpen(false); setReopenReason('');
    if (scorecardId) load(scorecardId);
  }, [scorecardId, load]);

  const payload = () => ({
    criteria: (card?.criteria || []).map(c => {
      const value = draft?.answers[c.criterion_id];
      return {
        criterion_id: c.criterion_id,
        rating: value?.answer && value.answer !== 'INSUFFICIENT' ? Number(value.answer) : null,
        insufficient_evidence: value?.answer === 'INSUFFICIENT',
        comment: value?.comment.trim() || null,
      };
    }),
    overall_recommendation: draft?.overall || null,
    strengths: draft?.strengths.trim() || null,
    concerns: draft?.concerns.trim() || null,
  });

  const act = async (action: () => Promise<{ data: Scorecard }>, message: string, fallback: string) => {
    if (busy) return false;
    try {
      setBusy(true); setError(null); setNotice(null);
      apply((await action()).data);
      setNotice(t(message));
      onChanged?.();
      return true;
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t(fallback));
      return false;
    } finally { setBusy(false); }
  };

  const save = () => card && act(() => scorecardApi.save(card.scorecard_id, payload()), "Đã lưu nháp scorecard.", "Không thể lưu scorecard");
  const submit = async () => {
    if (!card) return;
    // Persist the latest answers first so the server validates what the reviewer sees.
    const saved = await act(() => scorecardApi.save(card.scorecard_id, payload()), "Đã lưu nháp scorecard.", "Không thể lưu scorecard");
    if (saved) await act(() => scorecardApi.submit(card.scorecard_id), "Đã nộp scorecard.", "Không thể nộp scorecard");
  };

  const editable = !!card?.can_edit;
  const unanswered = (card?.criteria || []).filter(c => !draft?.answers[c.criterion_id]?.answer).length;

  const renderCriterion = (c: ScorecardCriterion) => {
    const value = draft?.answers[c.criterion_id] || { answer: null, comment: '' };
    const setValue = (next: Partial<typeof value>) => draft && setDraft({
      ...draft, answers: { ...draft.answers, [c.criterion_id]: { ...value, ...next } },
    });
    return (
      <Box key={c.criterion_id} sx={{ py: 1.5, borderTop: '1px solid #EDF1F5' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
          <Box sx={{ minWidth: 220, flex: 1 }}>
            {/* component="div": the Chip renders a <div>, which is not allowed inside <p>. */}
            <Typography component="div" variant="body2" fontWeight={600}>
              <Chip size="small" label={c.category === 'MUST_HAVE' ? t("Bắt buộc") : t("Ưu tiên")} sx={{ mr: 1, height: 20, fontSize: 11 }} />
              {c.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">{c.description}</Typography>
          </Box>
          <ToggleButtonGroup exclusive size="small" value={value.answer} disabled={!editable}
            aria-label={t("Đánh giá tiêu chí {0}", c.name)}
            onChange={(_, next: Answer) => setValue({ answer: next })}>
            {(['1', '2', '3', '4', '5'] as const).map(n => <ToggleButton key={n} value={n} aria-label={t("{0} điểm", n)}>{n}</ToggleButton>)}
            <ToggleButton value="INSUFFICIENT">{t("Thiếu bằng chứng")}</ToggleButton>
          </ToggleButtonGroup>
        </Box>
        {(editable || value.comment) && (
          <TextField fullWidth size="small" sx={{ mt: 1 }} label={t("Nhận xét (tùy chọn)")} value={value.comment}
            disabled={!editable} onChange={e => setValue({ comment: e.target.value })} inputProps={{ maxLength: 2000 }} />
        )}
      </Box>
    );
  };

  return (
    <Dialog open={!!scorecardId} onClose={() => !busy && onClose()} maxWidth="md" fullWidth>
      <DialogTitle>
        {/* DialogTitle is already an <h2>; a nested heading element (<h6>) is invalid HTML. */}
        <Typography component="span" variant="h6" color="#0A2B57" sx={{ display: 'block' }}>{t("Scorecard")} — {card?.candidate_name || t("Ứng viên")}</Typography>
        {card && (
          <Typography variant="caption" color="text.secondary">
            {card.position_title} · {t("Người chấm")}: {card.reviewer_name || 'Hiring Manager'} · {t("Bộ tiêu chí phiên bản {0}", card.criteria_version_number ?? '—')}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
        {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
        {loading || !card || !draft ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>{loading ? <CircularProgress size={28} /> : null}</Box>
        ) : (
          <>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip size="small" color={card.status === 'SUBMITTED' ? 'success' : card.status === 'IN_PROGRESS' ? 'warning' : 'default'}
                label={t(SCORECARD_STATUS_LABELS[card.status])} />
              <Chip size="small" color={card.is_overdue ? 'error' : 'default'}
                label={`${card.is_overdue ? t("Quá hạn") : t("Hạn")}: ${new Date(card.due_at).toLocaleString(dateLocale)}`} />
              {card.submitted_at && <Chip size="small" label={t("Nộp lúc {0}", new Date(card.submitted_at).toLocaleString(dateLocale))} />}
              {card.share_status !== 'ACTIVE' && <Chip size="small" color="error" label={t("Shortlist đã bị thu hồi")} />}
            </Box>
            {card.reopened_at && card.status !== 'SUBMITTED' && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {t("HR đã mở lại scorecard")} ({card.reopened_by_name || 'HR'}, {new Date(card.reopened_at).toLocaleString(dateLocale)}): {card.reopen_reason}
              </Alert>
            )}
            {!card.criteria_version_id && (
              <Alert severity="info" sx={{ mb: 2 }}>{t("Hồ sơ chưa có kết quả đánh giá hợp lệ tại thời điểm chia sẻ nên chưa thể chấm. HR cần chia sẻ lại sau khi hồ sơ được đánh giá.")}</Alert>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              {t("Thang điểm: 1 = rất yếu … 5 = rất mạnh. Chọn “Thiếu bằng chứng” nếu hồ sơ không đủ thông tin để đánh giá tiêu chí.")}
            </Typography>
            {(card.criteria || []).map(renderCriterion)}
            <Divider sx={{ my: 2 }} />
            <Box sx={{ display: 'grid', gap: 2 }}>
              <TextField select required label={t("Khuyến nghị chung")} value={draft.overall} disabled={!editable}
                onChange={e => setDraft({ ...draft, overall: e.target.value as Recommendation })}>
                {(Object.keys(RECOMMENDATION_LABELS) as Recommendation[]).map(key => (
                  <MenuItem key={key} value={key}>{t(RECOMMENDATION_LABELS[key])}</MenuItem>
                ))}
              </TextField>
              <TextField multiline minRows={2} label={t("Điểm mạnh")} value={draft.strengths} disabled={!editable}
                onChange={e => setDraft({ ...draft, strengths: e.target.value })} inputProps={{ maxLength: 4000 }} />
              <TextField multiline minRows={2} label={t("Điểm cần lưu ý")} value={draft.concerns} disabled={!editable}
                onChange={e => setDraft({ ...draft, concerns: e.target.value })} inputProps={{ maxLength: 4000 }} />
            </Box>
            {editable && unanswered > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {t("Còn {0} tiêu chí chưa đánh giá. Cần đánh giá đủ và chọn khuyến nghị chung trước khi nộp.", unanswered)}
              </Typography>
            )}
            {reopenOpen && (
              <TextField fullWidth multiline minRows={2} sx={{ mt: 2 }} required label={t("Lý do mở lại")} value={reopenReason}
                onChange={e => setReopenReason(e.target.value)} inputProps={{ maxLength: 2000 }} />
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>{t("Đóng")}</Button>
        {card?.can_reopen && !reopenOpen && <Button color="warning" onClick={() => setReopenOpen(true)}>{t("Mở lại scorecard")}</Button>}
        {card?.can_reopen && reopenOpen && (
          <Button variant="contained" color="warning" disabled={busy || !reopenReason.trim()}
            onClick={async () => {
              if (await act(() => scorecardApi.reopen(card.scorecard_id, reopenReason.trim()), "Đã mở lại scorecard.", "Không thể mở lại scorecard")) {
                setReopenOpen(false); setReopenReason('');
              }
            }}>{t("Xác nhận mở lại")}</Button>
        )}
        {editable && <Button onClick={save} disabled={busy}>{t("Lưu nháp")}</Button>}
        {editable && <Button variant="contained" color="secondary" onClick={submit} disabled={busy || unanswered > 0 || !draft?.overall}>{t("Nộp scorecard")}</Button>}
      </DialogActions>
    </Dialog>
  );
}
