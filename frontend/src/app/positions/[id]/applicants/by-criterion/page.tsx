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
  // "Xác nhận tất cả dòng đang hiện": danh sách mục tiêu chốt tại lúc mở hộp
  // thoại, để danh sách HR nhìn thấy đúng là danh sách sẽ ghi.
  const [confirmAllOpen, setConfirmAllOpen] = useState(false);
  const [confirmAllTargets, setConfirmAllTargets] = useState<{ applicationId: string; resultId: string; name: string }[]>([]);
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkNotice, setBulkNotice] = useState<string | null>(null);
  // Cùng lý do với `reviewInFlight`: state `bulkProgress` chỉ đổi sau lần render
  // kế tiếp, nên hai cú bấm sát nhau đều thấy "chưa chạy" và cùng ghi N dòng.
  const bulkInFlight = useRef(false);
  const requested = useRef<Set<string>>(new Set());
  // Khoá một-lần-ghi giống trang hồ sơ: `saving` là state nên chỉ đổi sau khi
  // React vẽ lại — hai cú bấm sát nhau đều thấy "chưa lưu" và cùng gửi POST.
  const reviewInFlight = useRef(false);

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

  useEffect(() => { setVisibleCount(PAGE_SIZE); setBulkNotice(null); setBulkError(null); }, [criterionId]);

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

  // Những dòng mà "xác nhận tất cả" sẽ ghi: chỉ dòng **đang hiện**, đang chờ xác
  // minh và có `result_id`. Quyền xác minh đã nằm trong `stateOf`, nên dòng mà
  // HR không có quyền ghi không bao giờ lọt vào danh sách này.
  const confirmableRows = useMemo(() => visibleRows.flatMap(row => {
    const application = details[row.applicationId];
    const result = application ? lookupResult(application, criterionId) : undefined;
    if (stateOf(row) !== 'PENDING' || !result?.result_id) return [];
    return [{ applicationId: row.applicationId, resultId: result.result_id, name: row.candidateName }];
  }), [visibleRows, details, criterionId, stateOf]);

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

  /**
   * Ghi một review. Trả `busy` khi đã có lần ghi đang chạy — chỗ gọi phải phân
   * biệt với `failed`, nếu không cú bấm thứ hai bị bỏ qua sẽ hiện lỗi vô cớ.
   */
  const review = async (applicationId: string, resultId: string, decision: 'CONFIRMED' | 'REJECTED', comment?: string) => {
    // Chốt chặn phải là ref: state `saving` chưa kịp đổi khi hai cú bấm rơi vào
    // cùng một nhịp render. Review là bảng append-only, nên hai POST là hai dòng
    // quyết định cho cùng một tiêu chí của cùng một người.
    if (reviewInFlight.current) return 'busy' as const;
    reviewInFlight.current = true;
    setSaving(resultId);
    try {
      const response = await assessmentsApi.reviewCriterionResult(resultId, decision, comment);
      applyReview(applicationId, criterionId, response.data);
      return 'saved' as const;
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không lưu được đánh dấu. Vui lòng thử lại.'));
      return 'failed' as const;
    } finally {
      reviewInFlight.current = false;
      setSaving(null);
    }
  };

  const submitReject = async () => {
    if (!rejectTarget || !rejectReason.trim()) return;
    setRejectError(null);
    const outcome = await review(rejectTarget.applicationId, rejectTarget.resultId, 'REJECTED', rejectReason.trim());
    if (outcome === 'saved') {
      setRejectTarget(null);
      setRejectReason('');
    } else if (outcome === 'failed') {
      setRejectError(t('Không lưu được đánh dấu. Vui lòng thử lại.'));
    }
  };

  const openConfirmAll = () => {
    setBulkError(null);
    setBulkNotice(null);
    setConfirmAllTargets(confirmableRows);
    setConfirmAllOpen(true);
  };

  /**
   * Một cú bấm, N dòng: vẫn là N quyết định riêng của HR, mỗi hồ sơ một POST,
   * ghi lần lượt để lịch sử append-only giữ nguyên một dòng cho mỗi hồ sơ.
   */
  const submitConfirmAll = async () => {
    if (bulkInFlight.current || confirmAllTargets.length === 0) return;
    bulkInFlight.current = true;
    const total = confirmAllTargets.length;
    setBulkError(null);
    setBulkNotice(null);
    setBulkProgress({ done: 0, total });
    let done = 0;
    try {
      for (const target of confirmAllTargets) {
        const outcome = await review(target.applicationId, target.resultId, 'CONFIRMED');
        if (outcome !== 'saved') throw new Error('review not saved');
        done += 1;
        setBulkProgress({ done, total });
      }
      setConfirmAllOpen(false);
      setConfirmAllTargets([]);
      setBulkNotice(t('Đã xác nhận {0} hồ sơ. Mỗi hồ sơ vẫn là một dòng riêng trong lịch sử.', done));
    } catch {
      // Các dòng trước đã ghi thật (append-only), nên bỏ chúng khỏi danh sách
      // còn lại: bấm lại chỉ ghi phần chưa xong, không ghi trùng.
      setConfirmAllTargets(previous => previous.slice(done));
      setBulkError(t('Đã xác nhận {0}/{1} hồ sơ; phần còn lại chưa ghi được.', done, total));
    } finally {
      bulkInFlight.current = false;
      setBulkProgress(null);
    }
  };

  // Mở hồ sơ từ đây không kèm hàng đợi. Hàng đợi "cần xác minh / ưu tiên duyệt"
  // không phải ngữ cảnh HR đang xem — họ đang duyệt theo một tiêu chí — nên mở
  // ra kèm hàng đợi đó chỉ làm bộ đếm "hồ sơ k/n" và prev/next trỏ sang những hồ
  // sơ không liên quan. Chỉ mang theo tiêu chí để sang đó là đứng đúng chỗ.
  const profileHref = (applicationId: string) => `/positions/${positionId}/applicants/${applicationId}#criterion-${criterionId}`;
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
      {bulkNotice && <Alert severity="success" sx={{ mb: 2 }} data-testid="criterion-confirm-all-done" onClose={() => setBulkNotice(null)}>{bulkNotice}</Alert>}

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
              {/* Một hành động cho đúng những dòng đang hiện: HR vẫn là người quyết
                  định, nhưng không phải bấm lại cùng một quyết định N lần. */}
              <Button
                size="small"
                variant="contained"
                color="secondary"
                startIcon={<CheckCircleOutlineIcon fontSize="small" />}
                data-testid="criterion-confirm-visible"
                disabled={confirmableRows.length === 0 || saving !== null || bulkProgress !== null}
                onClick={openConfirmAll}
              >
                {t('Xác nhận tất cả dòng đang hiện')}
              </Button>
              {bulkProgress && <CircularProgress size={18} />}
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

      <Dialog open={confirmAllOpen} onClose={() => { if (!bulkProgress) setConfirmAllOpen(false); }} maxWidth="xs" fullWidth data-testid="criterion-confirm-all-dialog">
        <DialogTitle sx={{ fontSize: 16 }}>{t('Xác nhận tất cả dòng đang hiện')}</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: 13, mb: 1 }}>
            {t('Sẽ ghi xác nhận cho {0} hồ sơ sau, mỗi hồ sơ một dòng riêng trong lịch sử:', confirmAllTargets.length)}
          </DialogContentText>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }} data-testid="criterion-confirm-all-list">
            {confirmAllTargets.slice(0, 10).map(target => (
              <li key={target.applicationId}>
                <Typography variant="body2" data-testid={`criterion-confirm-all-item-${target.applicationId}`}>{target.name}</Typography>
              </li>
            ))}
            {confirmAllTargets.length > 10 && (
              <li>
                <Typography variant="body2" color="text.secondary">{t('… và {0} hồ sơ khác', confirmAllTargets.length - 10)}</Typography>
              </li>
            )}
          </Box>
          {bulkError && <Alert severity="error" sx={{ mt: 1.5 }} data-testid="criterion-confirm-all-error">{bulkError}</Alert>}
          {bulkProgress && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }} data-testid="criterion-confirm-all-progress">
              {t('Đang ghi {0}/{1} hồ sơ…', bulkProgress.done, bulkProgress.total)}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmAllOpen(false)} disabled={Boolean(bulkProgress)}>{t('Hủy')}</Button>
          <Button
            variant="contained"
            color="secondary"
            data-testid="criterion-confirm-all-submit"
            disabled={confirmAllTargets.length === 0 || Boolean(bulkProgress)}
            onClick={() => void submitConfirmAll()}
          >
            {t('Xác nhận {0} hồ sơ', confirmAllTargets.length)}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
