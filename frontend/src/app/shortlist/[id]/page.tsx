'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, Stack, TextField, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import EvidenceCard from '@/components/candidates/EvidenceCard';
import CVDocumentViewer from '@/components/candidates/CVDocumentViewer';
import { useI18n } from '@/i18n/I18nProvider';
import { applicationsApi, shortlistApi } from '@/lib/api';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';
import { purgeShareDrafts, readDraft, removeDraft, shareFeedbackDraftKey, writeDraft } from '@/lib/localDrafts';
import ScorecardPanel from '@/components/shortlist/ScorecardPanel';

type Candidate = { application_id: string; candidate_name?: string; display_name?: string; matching_status?: string | null };
type Feedback = { feedback_id: string; author_name?: string; content: string; created_at: string };
type Share = { share_id: string; position_id: string; position?: { title?: string; position_code?: string }; created_by_profile?: { display_name?: string }; created_at?: string; status: string; allow_cv_view?: boolean; share_level_feedback_blocked?: boolean; note?: string; applications?: Candidate[]; feedback?: Feedback[] };

export default function ShareWorkspace() {
  const { t, dateLocale } = useI18n();
  const shareId = String(useParams().id);
  const [share, setShare] = useState<Share | null>(null);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [sending, setSending] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [evidence, setEvidence] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; data?: any; message?: string }>({ status: 'idle' });
  const [cv, setCv] = useState<{ status: 'idle' | 'loading' | 'ready' | 'error'; url?: string; isPdf?: boolean; message?: string }>({ status: 'idle' });
  const [cvPage, setCvPage] = useState(1);
  const [highlight, setHighlight] = useState('');
  const [scorecardProgress, setScorecardProgress] = useState<Record<string, number>>({});
  const [stale, setStale] = useState(false);
  const requestVersion = useRef(0);
  // Losing access must also drop everything typed locally for this share.
  const accessLost = useCallback(() => { requestVersion.current += 1; purgeShareDrafts(shareId); setFeedback(''); setLoading(false); setShare(null); setError('Quyền truy cập shortlist không còn hoặc shortlist không tồn tại.'); }, [shareId]);
  const [feedbackRestored, setFeedbackRestored] = useState(false);
  const load = useCallback(async (initial = false) => {
    const version = ++requestVersion.current;
    try {
      if (initial) setLoading(true);
      const result = await shortlistApi.getDetail(shareId);
      if (version !== requestVersion.current) return;
      const data: Share = result.data;
      setShare(data); setError('');
      setSelected(current => data.applications?.some(a => a.application_id === current) ? current : data.applications?.[0]?.application_id || '');
    } catch (err: any) {
      if (version !== requestVersion.current) return;
      if ([403, 404].includes(err.response?.status)) accessLost();
      else setError(err.response?.data?.detail || t('Không thể tải chi tiết shortlist.'));
    } finally { if (version === requestVersion.current) setLoading(false); }
  }, [shareId, t, accessLost]);
  useEffect(() => { void load(true); return () => { requestVersion.current += 1; }; }, [load]);
  useEffect(() => {
    const draft = readDraft<{ content: string }>(shareFeedbackDraftKey(shareId));
    if (draft?.content?.trim()) { setFeedback(draft.content); setFeedbackRestored(true); }
  }, [shareId]);
  useEffect(() => {
    // Persist after a pause so typing does not write to storage on every key.
    const content = feedback.trim();
    const timer = setTimeout(() => {
      if (content) writeDraft(shareFeedbackDraftKey(shareId), { content });
      else removeDraft(shareFeedbackDraftKey(shareId));
    }, 400);
    return () => clearTimeout(timer);
  }, [feedback, shareId]);
  useEffect(() => {
    let hiddenAt = 0;
    const check = () => {
      if (document.visibilityState === 'hidden') { hiddenAt = Date.now(); return; }
      // Returning after a short glance does not need a reload; longer absences
      // refresh silently and only show the banner when that refresh fails.
      if (Date.now() - hiddenAt < 30_000) return;
      setStale(true);
      void load();
    };
    document.addEventListener('visibilitychange', check);
    return () => document.removeEventListener('visibilitychange', check);
  }, [load]);
  useEffect(() => { if (share && !error) setStale(false); }, [share, error]);
  // Evidence and the CV are loaded only from the same share-scoped endpoint the
  // candidate page uses, so service-side allow_cv_view and snapshot rules stay authoritative.
  useEffect(() => {
    let live = true;
    setEvidence({ status: 'idle' }); setCv({ status: 'idle' }); setCvPage(1); setHighlight('');
    if (!selected) return;
    setEvidence({ status: 'loading' });
    applicationsApi.getById(selected).then(res => {
      if (!live) return;
      const data = res.data;
      setEvidence({ status: 'ready', data });
      if (data.can_view_cv) {
        setCv({ status: 'loading' });
        applicationsApi.getCvBlob(selected).then(file => {
          if (!live) return;
          const mime = data.documents?.[0]?.mime_type;
          const isPdf = file.data?.type === 'application/pdf' || mime === 'application/pdf';
          setCv({ status: 'ready', isPdf, url: isPdf ? URL.createObjectURL(file.data) : undefined });
        }).catch(err => {
          if (!live) return;
          if ([403, 404].includes(err.response?.status)) setCv({ status: 'error', message: 'Shortlist này không còn cho phép xem CV gốc.' });
          else setCv({ status: 'error', message: 'Không thể tải CV. Vui lòng thử lại.' });
        });
      }
    }).catch(err => {
      if (!live) return;
      if ([403, 404].includes(err.response?.status)) setEvidence({ status: 'error', message: 'Shortlist này không cho phép xem bằng chứng hoặc quyền truy cập đã thay đổi.' });
      else setEvidence({ status: 'error', message: err.response?.data?.detail || 'Không thể tải bằng chứng đánh giá.' });
    });
    return () => { live = false; };
  }, [selected]);
  useEffect(() => () => { if (cv.url) URL.revokeObjectURL(cv.url); }, [cv.url]);
  const submitFeedback = async () => {
    if (!feedback.trim() || sending) return;
    try {
      setSending(true); setError('');
      await shortlistApi.addFeedback(shareId, feedback.trim());
      removeDraft(shareFeedbackDraftKey(shareId)); setFeedbackRestored(false);
      setFeedback(''); await load();
    } catch (err: any) {
      if ([403, 404].includes(err.response?.status)) accessLost();
      else setError(err.response?.data?.detail || t('Không thể gửi phản hồi'));
    } finally { setSending(false); }
  };
  const matchingLabel = (status?: string | null) => ({ MEETS_MANDATORY: t('Đáp ứng bắt buộc'), NEEDS_HR_VERIFICATION: t('Cần HR xác minh'), POSSIBLE_MISMATCH: t('Cần xem xét'), NOT_ASSESSED: t('Chưa đánh giá') } as Record<string, string>)[status || ''] || t('Chưa đánh giá hoặc kết quả đã cũ');
  const unsavedMessage = t('Có thay đổi chưa lưu hoặc chưa gửi. Rời trang?');
  useUnsavedChangesGuard(dirty || !!feedback.trim(), unsavedMessage, { fallbackHref: '/shortlist' });
  if (loading) return <Box sx={{ textAlign: 'center', mt: 8 }}><CircularProgress /></Box>;
  if (!share) return <Box><Button component={Link} href="/shortlist">{t('Quay lại shortlist')}</Button><Alert severity="error">{t(error || 'Không thể tải chi tiết shortlist.')}</Alert></Box>;
  const candidate = share.applications?.find(a => a.application_id === selected);
  return <Box>
    <Button component={Link} href={`/shortlist?position=${encodeURIComponent(share.position_id)}`} sx={{ mb: 1 }}>← {t('Quay lại shortlist')}</Button>
    <Typography variant="h1" sx={{ fontSize: 28, mb: 1 }}>{t('Không gian đánh giá shortlist')} — {share.position?.title}</Typography>
    <Typography color="text.secondary" sx={{ mb: 2 }}>{share.position?.position_code} · {t('Chia sẻ bởi')} {share.created_by_profile?.display_name || 'HR'} {share.created_at ? `· ${new Date(share.created_at).toLocaleString(dateLocale)}` : ''}</Typography>
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
      <Chip label={share.status === 'ACTIVE' ? t('Đang hoạt động') : t('Đã thu hồi')} color={share.status === 'ACTIVE' ? 'success' : 'default'} />
      <Chip label={share.allow_cv_view ? t('Được xem CV') : t('Chỉ xem tóm tắt')} />
      <Button component={Link} href={`/positions/${share.position_id}?tab=jd`} size="small">{t('Xem JD hiện tại của vị trí')}</Button>
    </Stack>
    <Alert severity="info" sx={{ mb: 2 }}>{t('JD hiện tại có thể khác phiên bản dùng để đánh giá. Tiêu chí trong scorecard gắn với snapshot của từng ứng viên.')}</Alert>
    {share.note && <Alert severity="info" sx={{ mb: 2 }}><strong>{t('Ghi chú từ HR:')}</strong> {share.note}</Alert>}
    {error && <Alert severity="error" sx={{ mb: 2 }} action={<Button onClick={() => load()}>{t('Thử lại')}</Button>}>{t(error)}</Alert>}
    {stale && <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={() => load()}>{t('Tải lại')}</Button>}>
      {t('Dữ liệu có thể đã cũ sau khi bạn quay lại tab. Tải lại để thấy thay đổi hoặc thu hồi mới nhất.')}
    </Alert>}
    <Grid container spacing={2}>
      <Grid item xs={12} md={4}><Card variant="outlined"><CardContent>
        <Typography variant="h2" sx={{ fontSize: 19, mb: 1 }}>{t('Ứng viên được chia sẻ')} ({share.applications?.length || 0})</Typography>
        {!share.applications?.length && <Typography>{t('Không có dữ liệu ứng viên.')}</Typography>}
        <Stack spacing={1}>{share.applications?.map(a => <Button key={a.application_id} fullWidth variant={selected === a.application_id ? 'contained' : 'outlined'} aria-pressed={selected === a.application_id} onClick={() => setSelected(a.application_id)} sx={{ justifyContent: 'flex-start', textAlign: 'left', flexDirection: 'column', alignItems: 'flex-start', gap: 0 }}>
          <Box component="span">{a.candidate_name || a.display_name || t('Ứng viên')}</Box>
          <Box component="span" sx={{ fontSize: 11, fontWeight: 500, opacity: 0.8 }}>
            {matchingLabel(a.matching_status)}{typeof scorecardProgress[a.application_id] === 'number' ? ` · ${t('Scorecard {0}%', scorecardProgress[a.application_id])}` : ` · ${t('Scorecard chưa bắt đầu')}`}
          </Box>
        </Button>)}</Stack>
      </CardContent></Card></Grid>
      <Grid item xs={12} md={8}><Card variant="outlined"><CardContent>
        {/* Announce the switch for assistive tech without moving focus away from the list. */}
        <Box aria-live="polite" sx={{ position: 'absolute', left: 0, top: 0, width: 1, height: 1, margin: -1, padding: 0, border: 0, overflow: 'hidden', clip: 'rect(0 0 0 0)', clipPath: 'inset(50%)', whiteSpace: 'nowrap' }}>{candidate && t('Đang đánh giá {0}', candidate.candidate_name || candidate.display_name || t('ứng viên'))}</Box>
        {candidate && <><Typography variant="h2" sx={{ fontSize: 20, mb: 1 }}>{candidate.candidate_name || candidate.display_name || t('Ứng viên')}</Typography>
          <Button component={Link} href={`/positions/${share.position_id}/applicants/${candidate.application_id}?share=${encodeURIComponent(shareId)}`} sx={{ ml: 1, mb: 1 }} size="small">{t('Xem hồ sơ ứng viên')}</Button><br />
          <Chip size="small" sx={{ mb: 1 }} label={matchingLabel(candidate.matching_status)} />
        </>}
        <ScorecardPanel shareId={shareId} candidates={share.applications || []} selectedApplicationId={selected} onAccessLost={accessLost} onDirtyChange={setDirty}
          onProgress={(progress) => setScorecardProgress(current => {
            const keys = Object.keys(progress);
            return keys.length === Object.keys(current).length && keys.every(key => current[key] === progress[key]) ? current : progress;
          })} />
        {candidate && <Accordion disableGutters elevation={0} sx={{ mt: 1, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography fontWeight={600}>{t('CV và bằng chứng đánh giá')}</Typography></AccordionSummary>
          <AccordionDetails><Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              {evidence.status === 'loading' && <CircularProgress size={22} />}
              {evidence.status === 'error' && <Alert severity="info">{t(evidence.message || 'Không thể tải bằng chứng đánh giá.')}</Alert>}
              {evidence.status === 'ready' && <>{!evidence.data?.latest_assessment && <Typography variant="body2" color="text.secondary">{t('Chưa có đánh giá gắn với snapshot CV này.')}</Typography>}
                {!evidence.data?.can_view_assessment_evidence && evidence.data?.latest_assessment && <Alert severity="info" sx={{ mb: 1 }}>{t('Shortlist này chỉ cho phép xem tóm tắt, không cho xem đoạn trích bằng chứng.')}</Alert>}
                {(evidence.data?.latest_assessment?.criterion_results || []).filter((result: any) => result.evidence?.length || result.verbatim_quote).length
                  ? evidence.data.latest_assessment.criterion_results.map((result: any) => <Box key={result.criterion_id} sx={{ mb: 1.5 }}>
                      <EvidenceCard result={result} isPdf={Boolean(cv.isPdf)} hasCv={Boolean(cv.url)} selected={highlight === result.criterion_id}
                        onJumpToPage={(page, criterionId) => { setCvPage(page); setHighlight(criterionId); if (typeof document !== 'undefined') document.getElementById('shortlist-cv-viewer')?.scrollIntoView({ block: 'start' }); }} />
                    </Box>)
                  : evidence.data?.can_view_assessment_evidence && <Typography variant="body2" color="text.secondary">{t('Chưa có đoạn trích bằng chứng được duyệt cho ứng viên này. Không tự suy ra điểm phù hợp khi thiếu dữ liệu.')}</Typography>}
              </>}
            </Grid>
            <Grid item xs={12} md={6}>
              <Box id="shortlist-cv-viewer">
                {evidence.status === 'loading' && <CircularProgress size={22} />}
                {cv.status === 'loading' && <CircularProgress size={22} />}
                {cv.status === 'error' && <Alert severity="info">{t(cv.message || 'Không thể tải CV.')}</Alert>}
                {evidence.status === 'ready' && !evidence.data?.can_view_cv && <Alert severity="info">{t('Shortlist này không cho phép xem CV gốc.')}</Alert>}
                {evidence.data?.can_view_cv && cv.status === 'ready' && !cv.url && evidence.data?.documents?.[0] && <Button variant="outlined" onClick={() => applicationsApi.getCvBlob(selected).then(res => {
                  const href = URL.createObjectURL(res.data); const link = document.createElement('a'); link.href = href;
                  link.download = evidence.data.documents[0].original_filename || 'cv.docx'; link.click();
                  window.setTimeout(() => URL.revokeObjectURL(href), 1000);
                })}>{t('Tải CV gốc để xem')}</Button>}
                <CVDocumentViewer cvUrl={cv.status === 'ready' ? cv.url || null : null} cvError={cv.status === 'error' ? cv.message || null : null}
                  isPdf={Boolean(cv.isPdf)} canViewCv={Boolean(evidence.data?.can_view_cv)} selectedPage={cvPage} onPageChange={setCvPage} />
              </Box>
            </Grid>
          </Grid></AccordionDetails>
        </Accordion>}
      </CardContent></Card></Grid>
    </Grid>
    <Card variant="outlined" sx={{ my: 2 }}><CardContent>
      <Typography variant="h2" sx={{ fontSize: 19, mb: 1 }}>{t('Phản hồi chung')} ({share.feedback?.length || 0})</Typography>
      {!share.feedback?.length && <Typography color="text.secondary">{t('Chưa có phản hồi nào.')}</Typography>}
      {share.feedback?.map(f => <Box key={f.feedback_id} sx={{ my: 1 }}><Typography variant="caption">{f.author_name || t('Người dùng')} · {new Date(f.created_at).toLocaleString(dateLocale)}</Typography><Typography sx={{ whiteSpace: 'pre-wrap' }}>{f.content}</Typography></Box>)}
      {share.status === 'ACTIVE' && share.share_level_feedback_blocked && <Alert severity="info">{t('Shortlist đã thay đổi do retention; hãy yêu cầu HR tạo shortlist mới để gửi phản hồi chung')}</Alert>}
      {feedbackRestored && share.status === 'ACTIVE' && <Alert severity="info" sx={{ mt: 2 }} onClose={() => setFeedbackRestored(false)}>{t('Đã khôi phục phản hồi chưa gửi trên trình duyệt này.')}</Alert>}
      {share.status === 'ACTIVE' && !share.share_level_feedback_blocked && <><TextField fullWidth multiline rows={3} sx={{ mt: 2 }} label={t('Phản hồi của bạn')} value={feedback} onChange={e => setFeedback(e.target.value)} inputProps={{ maxLength: 3000 }} /><Button variant="contained" sx={{ mt: 1 }} onClick={submitFeedback} disabled={!feedback.trim() || sending}>{sending ? t('Đang gửi...') : t('Gửi phản hồi')}</Button></>}
    </CardContent></Card>
  </Box>;
}
