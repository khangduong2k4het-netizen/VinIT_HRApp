'use client';

import * as React from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, Collapse, Dialog, DialogActions, DialogContent, DialogTitle, Paper, TextField, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ReportProblemOutlinedIcon from '@mui/icons-material/ReportProblemOutlined';
import { useI18n } from '@/i18n/I18nProvider';
import { determineCriterionAction } from '@/lib/criterionAction';
import type { Criterion, CriterionResult } from '@/types';

const outcomeStyles: Record<string, { borderColor: string; label: string; color: string }> = {
  STRONG_MATCH: { borderColor: '#067647', label: 'Đáp ứng tốt', color: '#067647' },
  MATCH: { borderColor: '#0A2B57', label: 'Đáp ứng', color: '#0A2B57' },
  UNCLEAR: { borderColor: '#B54708', label: 'Chưa rõ', color: '#B54708' },
  NO_MATCH: { borderColor: '#C72127', label: 'Chưa đáp ứng', color: '#C72127' },
};

/**
 * The rubric text a reviewer needs in order to judge a verdict. The toggle sits
 * on the criterion-name row so it costs no vertical space; the panel opens in
 * flow underneath, never on top of the quote the reviewer is comparing against.
 */
function useCriterionRequirement(criterion?: Criterion) {
  const { t } = useI18n();
  const [open, setOpen] = React.useState(false);
  if (!criterion) return { toggle: null, panel: null };

  // A requirement spec is what the matcher actually measured; description and
  // guidance are the human-readable parts. Show whatever exists, in that order.
  const spec = criterion.requirement_spec;
  const specParts: string[] = [];
  if (spec) {
    if (spec.kind === 'YEARS' && spec.min_years != null) specParts.push(t('Tối thiểu {0} năm', spec.min_years));
    if (spec.kind === 'DEGREE' && spec.required_degree_level != null) specParts.push(t('Yêu cầu trình độ bậc {0}', spec.required_degree_level));
    if (spec.kind === 'LANGUAGE') {
      const langs = (spec.required_languages || []).join(', ');
      if (langs) specParts.push(t('Ngoại ngữ: {0}', langs));
      if (spec.required_ielts != null) specParts.push(`IELTS ${spec.required_ielts}`);
      if (spec.required_toeic != null) specParts.push(`TOEIC ${spec.required_toeic}`);
      if (spec.required_cefr) specParts.push(`CEFR ${spec.required_cefr}`);
    }
    if (spec.terms?.length) specParts.push(t('Từ khoá: {0}', spec.terms.join(', ')));
  }
  const hasBody = Boolean(criterion.description || criterion.evidence_guidance || criterion.jd_reference_text || specParts.length);
  if (!hasBody) return { toggle: null, panel: null };

  const toggle = (
    <Box
      component="button"
      type="button"
      data-testid="criterion-requirement-toggle"
      aria-expanded={open}
      aria-controls={`requirement-${criterion.criterion_id}`}
      onClick={() => setOpen(prev => !prev)}
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.25,
        background: 'none',
        border: 0,
        p: 0,
        cursor: 'pointer',
        color: '#0A2B57',
        font: 'inherit',
        fontSize: 11,
        lineHeight: 1,
        fontWeight: 600,
        whiteSpace: 'nowrap',
        '&:hover': { textDecoration: 'underline' },
      }}
    >
      <ExpandMoreIcon
        fontSize="small"
        sx={{ fontSize: 14, transition: 'transform .15s', transform: open ? 'rotate(180deg)' : 'none' }}
      />
      {t('Yêu cầu gốc')}
    </Box>
  );

  const panel = (
    <Collapse in={open} timeout="auto" unmountOnExit>
        <Paper
          elevation={0}
          id={`requirement-${criterion.criterion_id}`}
          sx={{ mt: 0.75, p: 1.5, backgroundColor: '#F8FAFC', borderLeft: '2px solid #CBD5E1', borderRadius: 1 }}
        >
          {criterion.description && (
            <Typography variant="body2" sx={{ fontSize: 13, lineHeight: 1.6 }}>{criterion.description}</Typography>
          )}
          {specParts.length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: criterion.description ? 0.75 : 0 }}>
              {specParts.join(' · ')}
            </Typography>
          )}
          {criterion.evidence_guidance && (
            <Typography variant="caption" sx={{ display: 'block', mt: 0.75, color: '#344054' }}>
              <strong>{t('Bằng chứng cần tìm:')}</strong> {criterion.evidence_guidance}
            </Typography>
          )}
          {criterion.jd_reference_text && (
            <Typography variant="caption" sx={{ display: 'block', mt: 0.75, fontStyle: 'italic', color: '#475467' }}>
              {t('Trích JD:')} “{criterion.jd_reference_text}”
            </Typography>
          )}
        </Paper>
    </Collapse>
  );

  return { toggle, panel };
}

interface EvidenceCardProps {
  result: CriterionResult;
  criterion?: Criterion;
  isPdf: boolean;
  hasCv: boolean;
  selected: boolean;
  /** Which of these the reviewer may record. Hidden when the profile is read-only. */
  canReview?: boolean;
  onReview?: (resultId: string, decision: 'CONFIRMED' | 'REJECTED', comment?: string) => Promise<void>;
  onJumpToPage: (page: number, criterionId: string) => void;
}

export default function EvidenceCard({ result, criterion, isPdf, hasCv, selected, canReview, onReview, onJumpToPage }: EvidenceCardProps) {
  const { t, dateLocale } = useI18n();
  const [savingReview, setSavingReview] = React.useState(false);
  const [reviewError, setReviewError] = React.useState<string | null>(null);
  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectReason, setRejectReason] = React.useState('');
  const latestReview = result.hr_reviews?.[0];
  const requirement = useCriterionRequirement(criterion);
  const action = determineCriterionAction(result);
  const style = outcomeStyles[result.outcome] || outcomeStyles.UNCLEAR;
  const citation = result.evidence?.[0];
  const verified = citation?.verification_status === 'VERIFIED' || citation?.verification_status === 'MANUAL_FIX';
  const page = citation?.page_number || result.page_number;
  const quote = result.verbatim_quote || citation?.verbatim_quote;
  // The citation is a button even before the CV is loaded — pressing it is what
  // triggers the fetch. It used to look actionable ("Trang 2 · Đã xác minh")
  // while doing nothing until the reviewer happened to press "Xem CV gốc".
  // Only a non-PDF has no page to jump to.
  const canJump = Boolean(page && isPdf);
  const cvNotLoaded = canJump && !hasCv;
  // FAILED means the quote was searched for and not found — a much stronger
  // signal than PENDING, which only means nobody has checked yet. Reporting both
  // as "Trích dẫn chưa xác minh" hid the difference the reviewer needs.
  const citationState = citation?.verification_status;
  const failed = citationState === 'FAILED';
  const confirmed = citationState === 'VERIFIED' || citationState === 'MANUAL_FIX';

  const citationLabel = failed
    ? t("Không tìm thấy trong CV")
    : confirmed
      ? (isPdf && page ? t("Trang {0} · Đã xác minh", page) : t("Đoạn trích đã xác minh"))
      : t("Chưa đối chiếu");
  const citationColor = failed ? '#B42318' : confirmed ? '#0A2B57' : '#667085';

  return (
    <Card
      className={`evidence-card ${result.outcome.toLowerCase().replace('_', '-')}`}
      data-testid="evidence-card"
      sx={{
        borderLeft: `4px solid ${style.borderColor}`,
        borderRadius: '0 8px 8px 0',
        boxShadow: selected ? '0 0 0 2px rgba(37,153,220,.35), 0 4px 14px rgba(10,43,87,.10)' : '0 1px 3px rgba(0,0,0,0.05)',
      }}
    >
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1, gap: 1 }}>
          <Box>
            <Chip label={t(style.label)} size="small" sx={{ backgroundColor: `${style.borderColor}15`, color: style.color, fontWeight: 700, fontSize: 11, height: 22, mr: 1, mb: 0.5 }} />
            <Chip label={result.category === 'MUST_HAVE' ? t("Bắt buộc") : t("Ưu tiên")} size="small" sx={{ backgroundColor: result.category === 'MUST_HAVE' ? '#FDF2F2' : '#E8F1FC', color: result.category === 'MUST_HAVE' ? '#941616' : '#0A2B57', fontWeight: 600, fontSize: 10, height: 22, mr: 1 }} />
            {result.decision_source && (
              <Chip
                label={`${t(result.decision_source === 'RULE' ? "Theo quy tắc xác định" : result.decision_source === 'HYBRID' ? "Quy tắc + AI" : "AI đối chiếu")}${result.evidence_strength != null ? ` · ${Math.round(result.evidence_strength * 100)}%` : ''}`}
                size="small"
                sx={{ backgroundColor: result.decision_source === 'RULE' ? '#ECFDF3' : result.decision_source === 'HYBRID' ? '#F4EBFF' : '#F2F4F7', color: result.decision_source === 'RULE' ? '#067647' : result.decision_source === 'HYBRID' ? '#6941C6' : '#344054', fontWeight: 600, fontSize: 10, height: 22 }}
              />
            )}
          </Box>
          {result.score !== null && <Typography variant="h6" sx={{ fontSize: 16, fontWeight: 'bold', color: style.color }}>{result.score}%</Typography>}
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body1" sx={{ fontWeight: 600, fontSize: 14 }}>{result.criterion_name}</Typography>
          {requirement.toggle}
        </Box>
        {requirement.panel}
        {/* One sentence saying what this criterion asks of the reviewer. Derived
            from data (outcome + citation state + a recorded decision), never from
            a model call, so it cannot invent a task that is not there.

            It sits on its own line right under the name on purpose: HR should not
            have to read the reasoning and the chips to work out whether anything
            is owed here. It costs one line per card, which is the price of not
            making people guess. */}
        {action.weight !== 'none' && (
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, mt: 0.5 }} data-testid={`criterion-action-${action.code}`}>
            {action.weight === 'act' ? (
              <ReportProblemOutlinedIcon sx={{ fontSize: 15, color: '#B42318', mt: '2px', flexShrink: 0 }} />
            ) : (
              <CheckCircleOutlineIcon sx={{ fontSize: 15, color: '#667085', mt: '2px', flexShrink: 0 }} />
            )}
            <Typography
              variant="caption"
              sx={{ fontSize: 12, lineHeight: 1.45, fontWeight: action.weight === 'act' ? 600 : 400, color: action.weight === 'act' ? '#B42318' : '#475467' }}
            >
              {action.code === 'NEEDS_CHECK' && page ? t(action.text, page) : t(action.text)}
            </Typography>
          </Box>
        )}
        {/* The engine's reasoning repeated what the action line now says ("chưa
            nêu số liệu trước/sau nên chưa xác minh được"), so it is kept only when
            it adds a fact — that is, when there is no action to state it for us. */}
        {result.reasoning && action.weight !== 'act' && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>{result.reasoning}</Typography>
        )}

        {quote ? (
          <Paper
            elevation={0}
            sx={{ backgroundColor: selected ? '#EFF8FF' : '#F8FAFC', borderLeft: '2px solid #E2E8F0', p: 1.5, borderRadius: 1, mt: 1, cursor: canJump ? 'pointer' : 'default', '&:hover': canJump ? { backgroundColor: '#F1F5F9' } : undefined }}
            role={canJump ? 'button' : undefined}
            tabIndex={canJump ? 0 : undefined}
            aria-label={canJump ? t("Mở trang {0} trong CV để kiểm tra bằng chứng", page || '') : undefined}
            data-testid="citation-quote"
            onClick={() => { if (canJump && page) onJumpToPage(page, result.criterion_id); }}
            onKeyDown={event => { if (canJump && page && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onJumpToPage(page, result.criterion_id); } }}
          >
            <Typography variant="body2" sx={{ fontStyle: 'italic', color: '#112434', fontSize: 13, lineHeight: 1.6 }}>&ldquo;{quote}&rdquo;</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 1, mt: 1, flexWrap: 'wrap' }}>
              <Chip
                data-testid={`citation-status-${citationState || 'UNKNOWN'}`}
                label={citationLabel}
                size="small"
                sx={{ backgroundColor: citationColor, color: 'white', fontWeight: 700, fontSize: 10, height: 20 }}
              />
              {canJump && (
                <Typography variant="caption" sx={{ fontSize: 11, color: '#475467' }}>
                  {cvNotLoaded ? t("Bấm để mở trang {0} trong CV", page || '') : t("Bấm để xem trong CV")}
                </Typography>
              )}
            </Box>
          </Paper>
        ) : (
          <Paper elevation={0} sx={{ backgroundColor: '#FFFAEB', p: 1.5, borderRadius: 1, mt: 1 }}>
            <Typography variant="body2" color="#B54708">{t("Chưa có bằng chứng được trích xuất cho tiêu chí này.")}</Typography>
          </Paper>
        )}

        {result.outcome === 'UNCLEAR' && <Alert severity="warning" icon={false} sx={{ mt: 2, py: 0, fontSize: 12 }}>{t("Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV để xác minh.")}</Alert>}

        {/* A criterion the engine flagged is not done until a person says they
            looked. This is where that happens — and it is the only thing that
            takes the application out of the "needs verification" queue, so HR is
            never pushed into a recruiting decision just to clear the queue. */}
        {result.requires_verification && (
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px dashed #E4E7EC' }} data-testid="criterion-review-block">
            {latestReview ? (
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                {latestReview.decision === 'CONFIRMED' ? (
                  <CheckCircleOutlineIcon sx={{ fontSize: 18, color: '#067647', mt: '1px' }} />
                ) : (
                  <ReportProblemOutlinedIcon sx={{ fontSize: 18, color: '#B42318', mt: '1px' }} />
                )}
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontSize: 13, fontWeight: 600 }} data-testid="criterion-reviewed">
                    {latestReview.decision === 'CONFIRMED'
                      ? t('Bạn đã xác nhận trích dẫn này đúng')
                      : t('Bạn đã đánh dấu trích dẫn này không đúng')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {latestReview.reviewer_name || t('HR')} · {new Date(latestReview.created_at).toLocaleString(dateLocale)}
                  </Typography>
                  {latestReview.comment && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: '#344054' }}>
                      {t('Lý do:')} {latestReview.comment}
                    </Typography>
                  )}
                  {canReview && onReview && result.result_id && (
                    <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                      {latestReview.decision === 'REJECTED' && (
                        <Button size="small" variant="text" sx={{ fontSize: 12 }}
                          onClick={async () => {
                            setSavingReview(true); setReviewError(null);
                            try { await onReview(result.result_id as string, 'CONFIRMED'); }
                            catch { setReviewError(t('Không lưu được xác nhận. Vui lòng thử lại.')); }
                            finally { setSavingReview(false); }
                          }}
                          disabled={savingReview}
                        >{t('Xác nhận lại là đúng')}</Button>
                      )}
                    </Box>
                  )}
                </Box>
              </Box>
            ) : canReview && onReview && result.result_id ? (
              <>
                {/* The heading and the explanation that used to live here now say
                    the same thing as the action line above ("Đối chiếu trích dẫn
                    với CV trang 3, rồi xác nhận"), and repeating it cost ~40px on
                    every flagged card. One statement of the task, buttons under it.
                    The status reassurance moved to the progress strip, where it
                    applies to the whole application rather than one criterion. */}
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Button
                    size="small" variant="outlined" startIcon={<CheckCircleOutlineIcon />}
                    data-testid="confirm-citation"
                    disabled={savingReview}
                    sx={{ borderColor: '#067647', color: '#067647', fontSize: 12 }}
                    onClick={async () => {
                      setSavingReview(true); setReviewError(null);
                      try { await onReview(result.result_id as string, 'CONFIRMED'); }
                      catch { setReviewError(t('Không lưu được xác nhận. Vui lòng thử lại.')); }
                      finally { setSavingReview(false); }
                    }}
                  >{savingReview ? t('Đang lưu...') : t('Trích dẫn đúng, đã kiểm')}</Button>
                  <Button
                    size="small" variant="text" startIcon={<ReportProblemOutlinedIcon />}
                    data-testid="reject-citation"
                    disabled={savingReview}
                    sx={{ color: '#B42318', fontSize: 12 }}
                    onClick={() => { setRejectReason(''); setRejectOpen(true); }}
                  >{t('Trích dẫn sai hoặc không có trong CV')}</Button>
                </Box>
              </>
            ) : (
              <Typography variant="caption" color="text.secondary">
                {t('Tiêu chí này đang chờ HR xác minh.')}
              </Typography>
            )}
            {reviewError && <Alert severity="error" sx={{ mt: 1, py: 0, fontSize: 12 }}>{reviewError}</Alert>}
          </Box>
        )}
      </CardContent>

      {/* A rejection must carry a reason: the next person to open this profile has
          to be able to act on it. Enforced by the API and by the table as well. */}
      <Dialog open={rejectOpen} onClose={() => setRejectOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: 16 }}>{t('Vì sao trích dẫn này không đúng?')}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth multiline minRows={3} size="small"
            label={t('Lý do (bắt buộc)')}
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
            inputProps={{ 'data-testid': 'reject-reason' }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectOpen(false)}>{t('Hủy')}</Button>
          <Button
            variant="contained" color="error"
            data-testid="reject-confirm"
            disabled={!rejectReason.trim() || savingReview}
            onClick={async () => {
              if (!result.result_id || !onReview) return;
              setSavingReview(true); setReviewError(null);
              try {
                await onReview(result.result_id, 'REJECTED', rejectReason.trim());
                setRejectOpen(false);
              } catch {
                setReviewError(t('Không lưu được đánh dấu. Vui lòng thử lại.'));
              } finally { setSavingReview(false); }
            }}
          >{t('Ghi lại')}</Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}
