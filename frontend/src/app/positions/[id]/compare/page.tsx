'use client';

import * as React from 'react';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Tooltip, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import { candidateReportsApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';
import ExportReportDialog from '@/components/reports/ExportReportDialog';

type Evidence = { quote: string; page_number: number | null; verified: boolean };
type Result = { outcome: string; score: number | null; requires_verification: boolean; evidence: Evidence[] };
type Criterion = { criterion_id: string; name: string; category: 'MUST_HAVE' | 'NICE_TO_HAVE'; effective_weight: number | null };
type Candidate = {
  application_id: string; candidate_name: string; application_status: string; rank_number: number | null;
  matching_status: string; matching_score: number | null; evidence_coverage: number | null; needs_verification: boolean;
  profile: Record<'education' | 'work' | 'certifications' | 'languages', string[]>;
  results: Record<string, Result>; strengths: string[]; to_clarify: string[];
};
type Comparison = {
  position: { position_id: string; title: string; position_code: string | null };
  criteria: Criterion[]; candidates: Candidate[]; best_by_criterion: Record<string, string[]>;
};

const OUTCOME: Record<string, { label: string; color: string; bg: string }> = {
  STRONG_MATCH: { label: 'Đáp ứng rõ', color: '#067647', bg: '#ECFDF3' },
  MATCH: { label: 'Đáp ứng', color: '#0A2B57', bg: '#EFF8FF' },
  UNCLEAR: { label: 'Chưa rõ', color: '#B54708', bg: '#FFFAEB' },
  NO_MATCH: { label: 'Chưa đáp ứng', color: '#C72127', bg: '#FEF3F2' },
};
const MATCHING: Record<string, string> = {
  MEETS_MANDATORY: 'Đáp ứng bắt buộc', NEEDS_HR_VERIFICATION: 'Cần HR xác minh',
  POSSIBLE_MISMATCH: 'Có dấu hiệu chưa đáp ứng', NOT_ASSESSED: 'Chưa đánh giá',
};
const PROFILE_ROWS: { key: keyof Candidate['profile']; label: string }[] = [
  { key: 'work', label: 'Kinh nghiệm' }, { key: 'education', label: 'Học vấn' },
  { key: 'certifications', label: 'Chứng chỉ' }, { key: 'languages', label: 'Ngoại ngữ' },
];

export default function CompareCandidatesPage() {
  const { t } = useI18n();
  const positionId = useParams().id as string;
  const [ids, setIds] = useState<string[]>([]);
  const [data, setData] = useState<Comparison | null>(null);
  const [error, setError] = useState('');
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    // Read ?ids= on the client only, so the page needs no Suspense boundary.
    const fromUrl = (new URLSearchParams(window.location.search).get('ids') || '').split(',').filter(Boolean);
    setIds(fromUrl);
    if (fromUrl.length < 2 || fromUrl.length > 4) {
      setError(t('Chọn từ 2 đến 4 hồ sơ để so sánh'));
      return;
    }
    candidateReportsApi.compare(positionId, fromUrl)
      .then(r => setData(r.data))
      .catch(e => setError(localizeServerMessage(e?.response?.data?.detail)));
  }, [positionId, t]);

  const back = <Button component={Link} href={`/positions/${positionId}/applicants`} startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>{t("Quay lại danh sách ứng viên")}</Button>;
  if (error) return <Box>{back}<Alert severity="error">{error}</Alert></Box>;
  if (!data) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>;

  const width = `${Math.floor(78 / data.candidates.length)}%`;
  const labelCell = (text: string, sub?: string) => (
    <TableCell component="th" scope="row" sx={{ width: '22%', fontWeight: 600, verticalAlign: 'top', backgroundColor: '#F8FAFC' }}>
      {text}{sub && <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{sub}</Typography>}
    </TableCell>
  );
  const section = (title: string) => (
    <TableRow><TableCell colSpan={data.candidates.length + 1} sx={{ backgroundColor: '#0A2B57', color: '#fff', fontWeight: 700, py: 1 }}>{title}</TableCell></TableRow>
  );
  const criterionRows = (category: Criterion['category']) => data.criteria.filter(c => c.category === category).map(c => (
    <TableRow key={c.criterion_id}>
      {labelCell(c.name, c.effective_weight != null ? t("Trọng số {0}%", c.effective_weight) : undefined)}
      {data.candidates.map(cand => {
        const result = cand.results[c.criterion_id];
        const meta = result ? OUTCOME[result.outcome] : undefined;
        const best = (data.best_by_criterion[c.criterion_id] || []).includes(cand.application_id);
        const quote = result?.evidence[0];
        return (
          <TableCell key={cand.application_id} sx={{ width, verticalAlign: 'top', border: best ? '2px solid #12B76A' : undefined }}>
            {meta ? <Chip size="small" label={t(meta.label)} sx={{ color: meta.color, backgroundColor: meta.bg, fontWeight: 700 }} />
              : <Chip size="small" label={t("Không có kết quả")} variant="outlined" />}
            {best && <Chip size="small" label={t("Tốt nhất")} sx={{ ml: 0.5, backgroundColor: '#12B76A', color: '#fff' }} />}
            {result?.requires_verification && <Chip size="small" variant="outlined" color="warning" label={t("Cần xác minh")} sx={{ ml: 0.5 }} />}
            {quote && (
              <Tooltip title={quote.quote}>
                <Typography variant="caption" color="text.secondary" sx={{ display: '-webkit-box', mt: 0.75, WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontStyle: 'italic' }}>
                  “{quote.quote}”{quote.page_number ? ` (${t("trang")} ${quote.page_number})` : ''}{!quote.verified ? ` · ${t("chưa xác minh")}` : ''}
                </Typography>
              </Tooltip>
            )}
          </TableCell>
        );
      })}
    </TableRow>
  ));
  const list = (items: string[]) => items.length
    ? <Box component="ul" sx={{ m: 0, pl: 2 }}>{items.map(item => <li key={item}><Typography variant="body2">{item}</Typography></li>)}</Box>
    : <Typography variant="body2" color="text.disabled">—</Typography>;

  return (
    <Box>
      {back}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        <Box>
          <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>{t("So sánh ứng viên song song")}</Typography>
          <Typography variant="body2" color="text.secondary">{data.position.position_code} · {data.position.title}</Typography>
        </Box>
        <Button variant="outlined" startIcon={<FileDownloadOutlinedIcon />} onClick={() => setExportOpen(true)}>{t("Xuất các hồ sơ này")}</Button>
      </Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        {t("Ô viền xanh là kết quả tốt nhất của tiêu chí đó trong nhóm đang so sánh (chỉ khi các ứng viên khác nhau). \"Chưa rõ\" nghĩa là chưa tìm thấy bằng chứng, không phải không đạt. Điểm một phần chỉ tính trên tiêu chí đã có bằng chứng; xem cùng độ phủ.")}
      </Alert>
      <TableContainer component={Paper} sx={{ borderRadius: 2 }}>
        <Table size="small" aria-label={t("So sánh ứng viên song song")}>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: '22%' }} />
              {data.candidates.map(c => (
                <TableCell key={c.application_id} sx={{ width, verticalAlign: 'top' }}>
                  <Typography component={Link} href={`/positions/${positionId}/applicants/${c.application_id}`} sx={{ fontWeight: 700, color: '#0A2B57' }}>{c.candidate_name}</Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {section(t("Tổng quan"))}
            <TableRow>{labelCell(t("Thứ hạng"))}{data.candidates.map(c => <TableCell key={c.application_id}>{c.rank_number ?? '—'}</TableCell>)}</TableRow>
            <TableRow>{labelCell(t("Trạng thái hồ sơ"))}{data.candidates.map(c => <TableCell key={c.application_id}>{isApplicationStatus(c.application_status) ? t(APPLICATION_STATUSES[c.application_status].label) : c.application_status}</TableCell>)}</TableRow>
            <TableRow>{labelCell(t("Kết luận AI"))}{data.candidates.map(c => <TableCell key={c.application_id}>{t(MATCHING[c.matching_status] || c.matching_status)}</TableCell>)}</TableRow>
            <TableRow>{labelCell(t("Điểm"))}{data.candidates.map(c => (
              <TableCell key={c.application_id}>
                <strong>{c.matching_score == null ? '—' : `${c.matching_score}%`}</strong>
                {c.matching_score != null && (c.evidence_coverage ?? 0) < 1 && <Chip size="small" label={t("một phần")} sx={{ ml: 0.5, height: 20, fontSize: 10, backgroundColor: '#FFFAEB', color: '#B54708' }} />}
              </TableCell>))}</TableRow>
            <TableRow>{labelCell(t("Độ phủ bằng chứng"))}{data.candidates.map(c => (
              <TableCell key={c.application_id}>
                {c.evidence_coverage == null ? '—' : `${Math.round(c.evidence_coverage * 100)}%`}
                {c.needs_verification && <Chip size="small" color="warning" variant="outlined" label={t("Cần xác minh")} sx={{ ml: 0.5 }} />}
              </TableCell>))}</TableRow>
            {data.criteria.some(c => c.category === 'MUST_HAVE') && section(t("Tiêu chí bắt buộc"))}
            {criterionRows('MUST_HAVE')}
            {data.criteria.some(c => c.category === 'NICE_TO_HAVE') && section(t("Tiêu chí ưu tiên"))}
            {criterionRows('NICE_TO_HAVE')}
            {section(t("Hồ sơ"))}
            {PROFILE_ROWS.map(row => (
              <TableRow key={row.key}>{labelCell(t(row.label))}{data.candidates.map(c => <TableCell key={c.application_id} sx={{ verticalAlign: 'top' }}>{list(c.profile[row.key] || [])}</TableCell>)}</TableRow>
            ))}
            {section(t("Gợi ý cho buổi phỏng vấn"))}
            <TableRow>{labelCell(t("Điểm mạnh nổi trội"))}{data.candidates.map(c => <TableCell key={c.application_id} sx={{ verticalAlign: 'top' }}>{list(c.strengths)}</TableCell>)}</TableRow>
            <TableRow>{labelCell(t("Cần làm rõ khi phỏng vấn"), t("Tiêu chí chưa rõ hoặc cần xác minh"))}{data.candidates.map(c => <TableCell key={c.application_id} sx={{ verticalAlign: 'top' }}>{list(c.to_clarify)}</TableCell>)}</TableRow>
          </TableBody>
        </Table>
      </TableContainer>
      <ExportReportDialog open={exportOpen} onClose={() => setExportOpen(false)} positionId={positionId}
        positionCode={data.position.position_code} selectedIds={ids} />
    </Box>
  );
}
