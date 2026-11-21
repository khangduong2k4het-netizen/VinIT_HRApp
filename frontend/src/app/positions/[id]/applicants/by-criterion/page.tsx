'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogContentText, DialogTitle, FormControl, IconButton, InputLabel, MenuItem,
  Select, TextField, Tooltip, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ReportProblemOutlinedIcon from '@mui/icons-material/ReportProblemOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { assessmentsApi, applicationsApi, criteriaApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { applicantProfileHref, type ApplicantQueue, type ApplicantSort } from '@/lib/applicantReview';
import { readApplicationCapabilities } from '@/lib/applicationCapabilities';
import { buildCriterionRows, countCriterionProgress, criterionRowState } from '@/lib/criterionQueue';
import type { ApplicationWithAssessment, Criterion, CriterionResult, RankingItem } from '@/types';

/**
 * Duyệt một tiêu chí trên nhiều hồ sơ.
 *
 * Mỗi dòng là một hồ sơ và một trích dẫn của cùng tiêu chí, quyết định ngay tại
 * dòng. Không có endpoint mới: danh sách lấy từ ranking (đã kèm kết quả từng
 * tiêu chí), còn trích dẫn + trạng thái đã kiểm lấy từ hồ sơ, và mọi lần ghi
 * vẫn là `POST /assessments/results/{id}/review`.
 */

const PAGE_SIZE = 8;

const OUTCOME_STYLES: Record<string, { label: string; color: string; background: string }> = {
  STRONG_MATCH: { label: 'Đáp ứng tốt', color: '#067647', background: '#ECFDF3' },
  MATCH: { label: 'Đáp ứng', color: '#0A2B57', background: '#E8F1FC' },
  UNCLEAR: { label: 'Chưa rõ', color: '#B54708', background: '#FFFAEB' },
  NO_MATCH: { label: 'Chưa đáp ứng', color: '#C72127', background: '#FEF3F2' },
};

function lookupResult(application: ApplicationWithAssessment | undefined, criterionId: string): CriterionResult | undefined {
  return application?.latest_assessment?.criterion_results?.find(result => result.criterion_id === criterionId);
}

function reviewedDecision(result: CriterionResult | undefined): 'CONFIRMED' | 'REJECTED' | null {
  const last = result?.hr_reviews?.[0];
  return last ? last.decision : null;
}

export default function ReviewByCriterionPage() {
  const { t } = useI18n();
  const params = useParams();
  const positionId = params.id as string;

  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [criterionId, setCriterionId] = useState<string>('');
  const [ranking, setRanking] = useState<RankingItem[]>([]);
  const [details, setDetails] = useState<Record<string, ApplicationWithAssessment>>({});
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [rejectTarget, setRejectTarget] = useState<{ applicationId: string; resultId: string } | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectError, setRejectError] = useState<string | null>(null);
  const requested = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([criteriaApi.getApproved(positionId), assessmentsApi.getLatestRanking(positionId)])
      .then(([criteriaResponse, rankingResponse]) => {
        if (cancelled) return;
        const approved: Criterion[] = criteriaResponse.data?.criteria || [];
        setCriteria(approved);
        // Mặc định tiêu chí đầu tiên còn việc, không phải tiêu chí đầu danh sách:
        // mở màn ra là thấy ngay chỗ cần làm.
        const ranked: RankingItem[] = rankingResponse.data || [];
        setRanking(ranked);
        const firstWithWork = approved.find(criterion => ranked.some(item => (item.criterion_results || [])
          .some(result => result.criterion_id === criterion.criterion_id && result.requires_verification)));
        setCriterionId((firstWithWork || approved[0])?.criterion_id || '');
        setError(null);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err.response?.data?.detail || t('Không thể tải danh sách hồ sơ cho tiêu chí này.'));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [positionId, t]);

  const rows = useMemo(() => buildCriterionRows(ranking, criterionId), [ranking, criterionId]);
  const visibleRows = useMemo(() => rows.slice(0, visibleCount), [rows, visibleCount]);

  // Chi tiết từng hồ sơ được tải theo đúng những dòng đang hiện: một tiêu chí có
  // thể có hàng trăm hồ sơ, tải hết ngay là hàng trăm request không ai đọc.
  useEffect(() => {
    const missing = visibleRows.map(row => row.applicationId).filter(id => !details[id] && !requested.current.has(id));
    if (missing.length === 0) return;
    missing.forEach(id => requested.current.add(id));
    setLoadingRows(true);
    Promise.all(missing.map(async id => {
      try {
        const response = await applicationsApi.getById(id);
        return response.data.position_id === positionId ? ([id, response.data] as const) : null;
      } catch {
        return null;
      }
    }))
      .then(loaded => {
        setDetails(previous => {
          const next = { ...previous };
          loaded.forEach(entry => { if (entry) next[entry[0]] = entry[1]; });
          return next;
        });
      })
      .finally(() => setLoadingRows(false));
  }, [visibleRows, details, positionId]);

  useEffect(() => { setVisibleCount(PAGE_SIZE); }, [criterionId]);

  const stateOf = useCallback((row: { applicationId: string; requiresVerification: boolean }) => {
    const application = details[row.applicationId];
    const result = application ? lookupResult(application, criterionId) : undefined;
    return criterionRowState({
      loaded: Boolean(application),
      requiresVerification: row.requiresVerification,
      hasResultId: Boolean(result?.result_id),
      reviewedDecision: reviewedDecision(result),
      canReview: application ? readApplicationCapabilities(application).reviewEvidence : false,
    });
  }, [details, criterionId]);

  const progress = useMemo(() => countCriterionProgress(rows, stateOf), [rows, stateOf]);

  const applyReview = (applicationId: string, criterionIdToUpdate: string, review: { review_id: string; decision: 'CONFIRMED' | 'REJECTED'; comment?: string | null; reviewer_user_id: string; reviewer_name?: string | null; created_at: string }) => {
    setDetails(previous => {
      const application = previous[applicationId];
      if (!application?.latest_assessment) return previous;
      return {
        ...previous,
        [applicationId]: {
          ...application,
          latest_assessment: {
            ...application.latest_assessment,
            criterion_results: application.latest_assessment.criterion_results.map(result => (result.criterion_id === criterionIdToUpdate
              ? { ...result, hr_reviews: [review, ...(result.hr_reviews || [])] }
              : result)),
          },
        },
      };
    });
  };

  const review = async (applicationId: string, resultId: string, decision: 'CONFIRMED' | 'REJECTED', comment?: string) => {
    setSaving(resultId);
    try {
      const response = await assessmentsApi.reviewCriterionResult(resultId, decision, comment);
      applyReview(applicationId, criterionId, response.data);
      return true;
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không lưu được đánh dấu. Vui lòng thử lại.'));
      return false;
    } finally {
      setSaving(null);
    }
  };

  const submitReject = async () => {
    if (!rejectTarget || !rejectReason.trim()) return;
    setRejectError(null);
    const saved = await review(rejectTarget.applicationId, rejectTarget.resultId, 'REJECTED', rejectReason.trim());
    if (saved) {
      setRejectTarget(null);
      setRejectReason('');
    } else {
      setRejectError(t('Không lưu được đánh dấu. Vui lòng thử lại.'));
    }
  };

  const profileHref = (applicationId: string) => `${applicantProfileHref(positionId, applicationId, 'NEEDS_VERIFICATION' as ApplicantQueue, 'REVIEW_PRIORITY' as ApplicantSort, '')}#criterion-${criterionId}`;
  const activeCriterion = criteria.find(criterion => criterion.criterion_id === criterionId);
  const outcomeStyle = (outcome: string | null) => (outcome ? OUTCOME_STYLES[outcome] : undefined);

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;
  }

  return (
    <Box>
      <Button component={Link} href={`/positions/${positionId}/applicants`} startIcon={<ArrowBackIcon />} sx={{ color: '#0A2B57', mb: 2 }}>
        {t('Quay lại danh sách ứng viên')}
      </Button>

      <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>
        {t('Duyệt một tiêu chí trên nhiều hồ sơ')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('Mỗi dòng là một hồ sơ cùng trích dẫn của tiêu chí đang chọn: đọc rồi xác nhận hoặc đánh dấu sai ngay tại dòng, không phải mở từng hồ sơ.')}
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}

      {criteria.length === 0 ? (
        <Alert severity="info">{t('Vị trí chưa có tiêu chí nào được duyệt.')}</Alert>
      ) : (
        <>
          <Card sx={{ mb: 2 }}>
            <CardContent sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', py: 1.5, '&:last-child': { pb: 1.5 } }}>
              <FormControl size="small" sx={{ minWidth: 280 }} data-testid="criterion-select">
                <InputLabel id="criterion-select-label">{t('Tiêu chí')}</InputLabel>
                <Select
                  labelId="criterion-select-label"
                  label={t('Tiêu chí')}
                  value={criterionId}
                  onChange={event => setCriterionId(event.target.value)}
                >
                  {criteria.map(criterion => (
                    <MenuItem key={criterion.criterion_id} value={criterion.criterion_id}>
                      {criterion.name}{criterion.category === 'MUST_HAVE' ? ` · ${t('Bắt buộc')}` : ''}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Chip
                size="small"
                data-testid="criterion-queue-progress"
                label={t('Đã xác minh {0}/{1} hồ sơ theo tiêu chí này', progress.verified, progress.flagged)}
                sx={{ backgroundColor: progress.verified === progress.flagged ? '#ECFDF3' : '#FFFAEB', color: progress.verified === progress.flagged ? '#067647' : '#B54708', fontWeight: 700 }}
              />
              <Typography variant="caption" color="text.secondary" data-testid="criterion-queue-count">
                {t('Hiển thị {0}/{1} hồ sơ', visibleRows.length, rows.length)}
              </Typography>
              {activeCriterion?.description && (
                <Tooltip title={activeCriterion.description}>
                  <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {activeCriterion.description}
                  </Typography>
                </Tooltip>
              )}
            </CardContent>
          </Card>

          {rows.length === 0 ? (
            <Alert severity="info">{t('Không có hồ sơ nào có kết quả cho tiêu chí này.')}</Alert>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {visibleRows.map(row => {
                const application = details[row.applicationId];
                const result = application ? lookupResult(application, criterionId) : undefined;
                const state = stateOf(row);
                const decision = reviewedDecision(result);
                const style = outcomeStyle(row.outcome);
                const quote = result?.evidence?.[0]?.verbatim_quote || result?.verbatim_quote || null;
                const page = result?.evidence?.[0]?.page_number || result?.page_number || null;
                const pending = state === 'PENDING';
                return (
                  <Card key={row.applicationId} data-testid={`criterion-row-${row.applicationId}`} sx={{ border: pending ? '1px solid #FEDF89' : '1px solid #E4E7EC' }}>
                    <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
                        <Box sx={{ minWidth: 220 }}>
                          <Typography variant="subtitle2" sx={{ color: '#0A2B57' }}>
                            {row.candidateName}
                            {row.rankNumber != null && <Typography component="span" variant="caption" color="text.secondary"> · #{row.rankNumber}</Typography>}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {t('Điểm tổng hợp')} {row.matchingScore == null ? '—' : `${row.matchingScore}%`} · {t('Độ phủ bằng chứng')} {row.evidenceCoverage == null ? '—' : `${Math.round(row.evidenceCoverage * 100)}%`}
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                          {style && (
                            <Chip size="small" label={t(style.label)} data-testid={`criterion-outcome-${row.applicationId}`} sx={{ backgroundColor: style.background, color: style.color, fontWeight: 700, fontSize: 11 }} />
                          )}
                          {state === 'LOADING' && <Chip size="small" label={t('Đang tải trích dẫn…')} />}
                          {state === 'NOT_REQUIRED' && <Chip size="small" label={t('Không cần xác minh')} data-testid={`criterion-not-required-${row.applicationId}`} />}
                          {state === 'NO_RESULT' && <Chip size="small" label={t('Không có kết quả để ghi cho tiêu chí này')} />}
                          {state === 'NO_PERMISSION' && <Chip size="small" label={t('Không có quyền xác minh hồ sơ này')} data-testid={`criterion-no-permission-${row.applicationId}`} />}
                          {state === 'REVIEWED' && (
                            <Chip
                              size="small"
                              data-testid={`criterion-reviewed-${row.applicationId}`}
                              label={decision === 'REJECTED' ? t('Đã đánh dấu sai') : t('Đã xác nhận')}
                              sx={{ backgroundColor: decision === 'REJECTED' ? '#FEF3F2' : '#ECFDF3', color: decision === 'REJECTED' ? '#B42318' : '#067647', fontWeight: 700 }}
                            />
                          )}
                          <Button
                            component={Link}
                            href={profileHref(row.applicationId)}
                            size="small"
                            endIcon={<OpenInNewIcon fontSize="small" />}
                            data-testid={`criterion-open-profile-${row.applicationId}`}
                            sx={{ px: 0.75, minWidth: 0 }}
                          >
                            {t('Mở hồ sơ')}
                          </Button>
                        </Box>
                      </Box>

                      <Box sx={{ mt: 1 }}>
                        {state === 'LOADING' ? (
                          <Typography variant="body2" color="text.secondary">{t('Đang tải trích dẫn…')}</Typography>
                        ) : quote ? (
                          <Typography variant="body2" sx={{ fontStyle: 'italic' }} data-testid={`criterion-quote-${row.applicationId}`}>
                            “{quote}”
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">{t('Không tìm thấy trích dẫn cho tiêu chí này.')}</Typography>
                        )}
                        {page != null && (
                          <Typography variant="caption" color="text.secondary">{t('Trang {0}', page)}</Typography>
                        )}
                      </Box>

                      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                        <Button
                          size="small"
                          variant="contained"
                          color="secondary"
                          startIcon={<CheckCircleOutlineIcon fontSize="small" />}
                          data-testid={`criterion-confirm-${row.applicationId}`}
                          disabled={!pending || saving !== null}
                          onClick={() => { if (result?.result_id) void review(row.applicationId, result.result_id, 'CONFIRMED'); }}
                        >
                          {t('Xác nhận')}
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={<ReportProblemOutlinedIcon fontSize="small" />}
                          data-testid={`criterion-reject-${row.applicationId}`}
                          disabled={!pending || saving !== null}
                          onClick={() => {
                            if (!result?.result_id) return;
                            setRejectTarget({ applicationId: row.applicationId, resultId: result.result_id });
                            setRejectReason(''); setRejectError(null);
                          }}
                        >
                          {t('Đánh dấu sai')}
                        </Button>
                        {saving === result?.result_id && <CircularProgress size={18} />}
                      </Box>
                    </CardContent>
                  </Card>
                );
              })}
              {rows.length > visibleRows.length && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                  <Button variant="outlined" onClick={() => setVisibleCount(count => count + PAGE_SIZE)} data-testid="criterion-load-more">
                    {t('Tải thêm {0} hồ sơ', Math.min(PAGE_SIZE, rows.length - visibleRows.length))}
                  </Button>
                </Box>
              )}
              {loadingRows && visibleRows.some(row => !details[row.applicationId]) && (
                <Typography variant="caption" color="text.secondary">{t('Đang tải trích dẫn của các hồ sơ đang hiện…')}</Typography>
              )}
            </Box>
          )}
        </>
      )}

      <Dialog open={Boolean(rejectTarget)} onClose={() => !saving && setRejectTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: 16 }}>{t('Vì sao trích dẫn này không đúng?')}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: 13, mb: 1 }}>
            {t('Lý do được lưu cùng quyết định, để người mở hồ sơ sau hiểu vì sao bằng chứng bị đánh dấu sai.')}
          </DialogContentText>
          {rejectError && <Alert severity="error" sx={{ mb: 1 }}>{t(rejectError)}</Alert>}
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={3}
            size="small"
            label={t('Lý do (bắt buộc)')}
            value={rejectReason}
            onChange={event => setRejectReason(event.target.value)}
            inputProps={{ 'data-testid': 'criterion-reject-reason', maxLength: 1000 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectTarget(null)} disabled={saving !== null}>{t('Hủy')}</Button>
          <Button
            variant="contained"
            color="error"
            data-testid="criterion-reject-confirm"
            disabled={!rejectReason.trim() || saving !== null}
            onClick={() => void submitReject()}
          >
            {saving ? t('Đang lưu…') : t('Ghi lại')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
