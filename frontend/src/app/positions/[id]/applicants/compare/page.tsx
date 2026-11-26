'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, Grid, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import { applicationsApi, positionsApi, type DuplicateSignal } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import CVDocumentViewer from '@/components/candidates/CVDocumentViewer';
import { extractDocxBlocks, type DocxBlock } from '@/lib/docxText';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';
import { COVERAGE_THRESHOLD } from '@/lib/applicantReview';
import { readApplicationCapabilities } from '@/lib/applicationCapabilities';
import { DUPLICATE_SIGNAL_LABELS, differingOutcomes, pairSignal } from '@/lib/duplicateCompare';
import type { ApplicationWithAssessment, CriterionResult } from '@/types';

/**
 * So sánh hai hồ sơ bị gắn cờ trùng, cạnh nhau.
 *
 * Mỗi bên giữ CV riêng và con trỏ trang riêng: bấm một trích dẫn chỉ nhảy khung
 * CV của bên đó, nên HR đối chiếu được hai tệp ở hai trang khác nhau — đúng thứ
 * không làm được khi mở A rồi mở B. Không có hành động ghi nào ở đây: màn này để
 * quyết định, mọi thay đổi trạng thái vẫn nằm ở hồ sơ.
 */

const OUTCOME_STYLES: Record<string, { label: string; color: string; background: string }> = {
  STRONG_MATCH: { label: 'Đáp ứng tốt', color: '#067647', background: '#ECFDF3' },
  MATCH: { label: 'Đáp ứng', color: '#0A2B57', background: '#E8F1FC' },
  UNCLEAR: { label: 'Chưa rõ', color: '#B54708', background: '#FFFAEB' },
  NO_MATCH: { label: 'Chưa đáp ứng', color: '#C72127', background: '#FEF3F2' },
};

interface SideCv {
  url: string | null;
  page: number;
  requested: boolean;
  loading: boolean;
  error: string | null;
  docx: DocxBlock[] | null;
  docxError: string | null;
  jump: (page: number) => void;
  load: () => void;
}

/**
 * CV của một bên. Tải khi HR yêu cầu (hoặc khi bấm một trích dẫn), và đổi hồ sơ
 * là bỏ bản cũ — so sánh nhầm tệp của ứng viên khác là kết luận sai.
 */
function useSideCv(application: ApplicationWithAssessment | null): SideCv {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [requested, setRequested] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docx, setDocx] = useState<DocxBlock[] | null>(null);
  const [docxError, setDocxError] = useState<string | null>(null);
  const blobUrl = useRef<string | null>(null);
  const applicationId = application?.application_id || null;
  const documents = application?.documents;

  useEffect(() => {
    if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; }
    setUrl(null); setPage(1); setRequested(false); setLoading(false); setError(null);
    setDocx(null); setDocxError(null);
    return () => { if (blobUrl.current) { URL.revokeObjectURL(blobUrl.current); blobUrl.current = null; } };
  }, [applicationId]);

  const load = useCallback(async () => {
    if (!applicationId || loading) return;
    setRequested(true);
    if (url) return;
    setLoading(true); setError(null);
    try {
      const file = await applicationsApi.getCvBlob(applicationId);
      if (blobUrl.current) URL.revokeObjectURL(blobUrl.current);
      blobUrl.current = URL.createObjectURL(file.data);
      setUrl(blobUrl.current);
      const document = documents?.[0];
      const isPdfFile = document?.mime_type === 'application/pdf' || /\.pdf$/i.test(document?.original_filename || '');
      if (!isPdfFile) {
        try {
          const bytes = file.data instanceof Blob ? await file.data.arrayBuffer() : file.data;
          setDocx(await extractDocxBlocks(bytes)); setDocxError(null);
        } catch {
          setDocx(null);
          setDocxError(t('Không đọc được nội dung tệp DOCX này trong trình duyệt. Hãy tải CV gốc để xem đầy đủ.'));
        }
      }
    } catch {
      setUrl(null); setError(t('Không thể tải CV gốc. Vui lòng thử lại sau.'));
    } finally { setLoading(false); }
  }, [applicationId, documents, loading, t, url]);

  const jump = useCallback((target: number) => {
    if (target < 1) return;
    setPage(target);
    if (!url) void load();
  }, [load, url]);

  return { url, page, requested, loading, error, docx, docxError, jump, load };
}

function isPdfDocument(application: ApplicationWithAssessment | null): boolean {
  const document = application?.documents?.[0];
  return document?.mime_type === 'application/pdf' || /\.pdf$/i.test(document?.original_filename || '');
}

function SideIdentity({ application, testId }: { application: ApplicationWithAssessment; testId: string }) {
  const { t } = useI18n();
  const document = application.documents?.[0];
  const status = isApplicationStatus(application.application_status) ? APPLICATION_STATUSES[application.application_status] : null;
  return (
    <Card data-testid={testId} sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="h2" sx={{ fontSize: 20, color: '#0A2B57' }}>
              {application.identity?.display_name || t('Hồ sơ ứng viên')}
            </Typography>
            <Typography variant="caption" color="text.secondary" fontFamily="monospace">
              ID: {application.application_id.slice(0, 8)}...
            </Typography>
          </Box>
          {status && <Chip size="small" label={t(status.label)} sx={{ fontWeight: 700 }} />}
        </Box>
        <Box sx={{ mt: 1.5, display: 'grid', gap: 0.5 }}>
          <Typography variant="body2" data-testid={`${testId}-email`}>
            <Box component="span" sx={{ color: 'text.secondary' }}>{t('Email')}: </Box>
            {application.identity?.email || t('Chưa có email')}
          </Typography>
          <Typography variant="body2" data-testid={`${testId}-phone`}>
            <Box component="span" sx={{ color: 'text.secondary' }}>{t('Điện thoại')}: </Box>
            {application.identity?.phone || t('Chưa có số điện thoại')}
          </Typography>
          {document?.original_filename && (
            <Typography variant="caption" color="text.secondary" fontFamily="monospace">
              {t('Tệp gốc:')} {document.original_filename}
            </Typography>
          )}
        </Box>
        <Divider sx={{ my: 1.5 }} />
        <Box sx={{ display: 'flex', gap: 3 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">{t('Điểm tổng hợp')}</Typography>
            <Typography variant="h4" sx={{ fontSize: 22, fontWeight: 700, color: '#0A2B57' }}>
              {application.latest_assessment?.matching_score != null ? `${application.latest_assessment.matching_score}%` : '—'}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">{t('Độ phủ bằng chứng')}</Typography>
            <Typography variant="h4" sx={{ fontSize: 22, fontWeight: 700, color: (application.latest_assessment?.evidence_coverage || 0) >= COVERAGE_THRESHOLD ? '#067647' : '#B54708' }}>
              {application.latest_assessment?.evidence_coverage != null ? `${Math.round(application.latest_assessment.evidence_coverage * 100)}%` : '—'}
            </Typography>
          </Box>
        </Box>
        <Button
          component={Link}
          href={`/positions/${application.position_id}/applicants/${application.application_id}`}
          size="small"
          variant="outlined"
          sx={{ mt: 1.5 }}
          data-testid={`${testId}-open`}
        >
          {t('Mở hồ sơ đầy đủ')}
        </Button>
      </CardContent>
    </Card>
  );
}

function CriterionSide({ result, side, onOpenPage }: { result?: CriterionResult; side: 'left' | 'right'; onOpenPage: (page: number) => void }) {
  const { t } = useI18n();
  if (!result) {
    return (
      <Typography variant="body2" color="text.secondary" data-testid={`compare-side-${side}`}>
        {t('Không có kết quả cho tiêu chí này')}
      </Typography>
    );
  }
  const style = OUTCOME_STYLES[result.outcome] || { label: result.outcome, color: '#344054', background: '#F2F4F7' };
  const quote = result.evidence?.[0]?.verbatim_quote || result.verbatim_quote;
  const page = result.evidence?.[0]?.page_number || result.page_number || null;
  return (
    <Box data-testid={`compare-side-${side}`}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Chip
          size="small"
          label={t(style.label)}
          data-testid={`compare-outcome-${side}`}
          sx={{ backgroundColor: style.background, color: style.color, fontWeight: 700, fontSize: 11 }}
        />
        <Typography variant="caption" color="text.secondary">
          {result.score == null ? t('Không có điểm') : `${result.score}%`}
        </Typography>
        {page && (
          <Button
            size="small"
            onClick={() => onOpenPage(page)}
            data-testid={`compare-open-page-${side}`}
            sx={{ minWidth: 0, px: 0.5, fontSize: 11 }}
          >
            {t('Mở trang {0} trong CV', page)}
          </Button>
        )}
      </Box>
      {quote && (
        <Typography variant="body2" sx={{ mt: 0.5, fontStyle: 'italic', color: 'text.secondary' }}>
          “{quote}”
        </Typography>
      )}
    </Box>
  );
}

export default function CompareApplicantsPage() {
  const { t } = useI18n();
  const params = useParams();
  const positionId = params.id as string;
  const [pair, setPair] = useState<{ left: string; right: string } | null>(null);
  const [applications, setApplications] = useState<{ left: ApplicationWithAssessment | null; right: ApplicationWithAssessment | null }>({ left: null, right: null });
  const [signals, setSignals] = useState<DuplicateSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Cặp đang so nằm trong URL — mở lại, tải lại hay gửi cho đồng nghiệp vẫn
    // đúng hai hồ sơ này, không phải nhớ lại từ đầu.
    const search = new URLSearchParams(window.location.search);
    const left = search.get('left');
    const right = search.get('right');
    if (!left || !right) {
      setError(t('Cần chọn hai hồ sơ để so sánh.'));
      setLoading(false);
      return;
    }
    setPair({ left, right });
  }, [t]);

  useEffect(() => {
    if (!pair) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      applicationsApi.getById(pair.left),
      applicationsApi.getById(pair.right),
      positionsApi.getDuplicateSignals(positionId).catch(() => ({ data: [] as DuplicateSignal[] })),
    ])
      .then(([leftResponse, rightResponse, signalResponse]) => {
        if (cancelled) return;
        if (leftResponse.data?.position_id !== positionId || rightResponse.data?.position_id !== positionId) {
          setApplications({ left: null, right: null });
          setError(t('Hồ sơ không thuộc vị trí này'));
          return;
        }
        setApplications({ left: leftResponse.data, right: rightResponse.data });
        setSignals(signalResponse.data || []);
        setError(null);
      })
      .catch((err: any) => {
        if (cancelled) return;
        setApplications({ left: null, right: null });
        setError(err.response?.data?.detail || t('Không thể tải hai hồ sơ để so sánh.'));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pair, positionId, t]);

  const left = applications.left;
  const right = applications.right;
  const leftCv = useSideCv(left);
  const rightCv = useSideCv(right);
  const leftResults = useMemo(() => left?.latest_assessment?.criterion_results || [], [left]);
  const rightResults = useMemo(() => right?.latest_assessment?.criterion_results || [], [right]);

  const rows = useMemo(() => {
    const criterionIds = [...new Set([...leftResults.map(item => item.criterion_id), ...rightResults.map(item => item.criterion_id)])];
    return criterionIds.map(criterionId => ({
      criterionId,
      left: leftResults.find(item => item.criterion_id === criterionId),
      right: rightResults.find(item => item.criterion_id === criterionId),
      name: leftResults.find(item => item.criterion_id === criterionId)?.criterion_name
        || rightResults.find(item => item.criterion_id === criterionId)?.criterion_name
        || criterionId,
    }));
  }, [leftResults, rightResults]);
  const differing = differingOutcomes(leftResults, rightResults);
  const signal = pairSignal(signals, left?.application_id, right?.application_id);
  const signalLabel = signal?.signal_type ? (DUPLICATE_SIGNAL_LABELS[signal.signal_type] || signal.signal_type) : null;

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;
  }

  if (error) {
    return (
      <Box>
        <Button component={Link} href={`/positions/${positionId}/applicants?queue=DUPLICATE`} startIcon={<ArrowBackIcon />} sx={{ color: '#0A2B57', mb: 2 }}>
          {t('Quay lại hàng đợi hồ sơ trùng')}
        </Button>
        <Alert severity="error">{t(error)}</Alert>
      </Box>
    );
  }

  if (!left || !right) {
    return <Alert severity="error">{t('Không tìm thấy hai hồ sơ để so sánh.')}</Alert>;
  }

  const mayViewCv = readApplicationCapabilities(left).viewCv && readApplicationCapabilities(right).viewCv;

  return (
    <Box>
      <Button component={Link} href={`/positions/${positionId}/applicants?queue=DUPLICATE`} startIcon={<ArrowBackIcon />} sx={{ color: '#0A2B57', mb: 2 }}>
        {t('Quay lại hàng đợi hồ sơ trùng')}
      </Button>

      <Box sx={{ mb: 2 }} data-testid="compare-header">
        <Typography variant="h1" sx={{ fontSize: 24, color: '#0A2B57', mb: 0.5 }}>
          {t('So sánh hai hồ sơ bị gắn cờ trùng')}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {signalLabel && (
            <Chip
              size="small"
              icon={<CompareArrowsIcon />}
              data-testid="compare-signal"
              label={signal?.confidence != null ? t('{0} · độ tin cậy {1}%', signalLabel, Math.round(signal.confidence * 100)) : signalLabel}
              sx={{ backgroundColor: '#FFFAEB', color: '#B54708', fontWeight: 600 }}
            />
          )}
          <Chip
            size="small"
            data-testid="compare-differing"
            label={differing.length > 0 ? t('Khác kết luận ở {0}/{1} tiêu chí', differing.length, rows.length) : t('Cả {0} tiêu chí kết luận giống nhau', rows.length)}
            sx={{ backgroundColor: differing.length > 0 ? '#FEF3F2' : '#ECFDF3', color: differing.length > 0 ? '#B42318' : '#067647', fontWeight: 700 }}
          />
        </Box>
      </Box>

      {/* Hai cột ở màn rộng, xếp chồng trên điện thoại: mỗi bên vẫn giữ nguyên
          định danh, CV và con trỏ trang của mình. */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}><SideIdentity application={left} testId="compare-left" /></Grid>
        <Grid item xs={12} md={6}><SideIdentity application={right} testId="compare-right" /></Grid>
      </Grid>

      <Typography variant="h2" sx={{ fontSize: 18, color: '#0A2B57', mb: 1 }}>{t('CV gốc của từng bên')}</Typography>
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <CVDocumentViewer
            cvUrl={leftCv.url}
            cvError={leftCv.error}
            isPdf={isPdfDocument(left)}
            canViewCv={mayViewCv}
            selectedPage={leftCv.page}
            onPageChange={leftCv.jump}
            requested={leftCv.requested}
            loading={leftCv.loading}
            onRequest={leftCv.load}
            docxBlocks={leftCv.docx}
            docxError={leftCv.docxError}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <CVDocumentViewer
            cvUrl={rightCv.url}
            cvError={rightCv.error}
            isPdf={isPdfDocument(right)}
            canViewCv={mayViewCv}
            selectedPage={rightCv.page}
            onPageChange={rightCv.jump}
            requested={rightCv.requested}
            loading={rightCv.loading}
            onRequest={rightCv.load}
            docxBlocks={rightCv.docx}
            docxError={rightCv.docxError}
          />
        </Grid>
      </Grid>

      <Typography variant="h2" sx={{ fontSize: 18, color: '#0A2B57', mb: 1 }}>{t('Kết quả đánh giá theo tiêu chí')}</Typography>
      {rows.length === 0 ? (
        <Alert severity="info">{t('Chưa có kết quả đánh giá cho hai hồ sơ này')}</Alert>
      ) : rows.map(row => {
        const differs = differing.includes(row.criterionId);
        return (
          <Card
            key={row.criterionId}
            data-testid={`compare-criterion-${row.criterionId}`}
            sx={{ mb: 1.5, border: differs ? '1px solid #FDA29B' : '1px solid #E4E7EC' }}
          >
            <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <Typography variant="subtitle2">{row.name}</Typography>
                {differs && (
                  <Chip size="small" data-testid={`compare-differs-${row.criterionId}`} label={t('Khác kết luận')} sx={{ backgroundColor: '#FEF3F2', color: '#B42318', fontWeight: 700, fontSize: 11 }} />
                )}
              </Box>
              <Grid container spacing={2} sx={{ mt: 0.25 }}>
                <Grid item xs={12} sm={6}><CriterionSide side="left" result={row.left} onOpenPage={leftCv.jump} /></Grid>
                <Grid item xs={12} sm={6}><CriterionSide side="right" result={row.right} onOpenPage={rightCv.jump} /></Grid>
              </Grid>
            </CardContent>
          </Card>
        );
      })}
    </Box>
  );
}
