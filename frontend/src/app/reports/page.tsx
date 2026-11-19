'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, MenuItem, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { analyticsApi, positionsApi } from '@/lib/api';
import type { Position } from '@/types';

interface OverrideCase {
  event_id: string; changed_at: string; application_id: string; position_id: string; position_title: string; position_code: string;
  candidate_name?: string | null; ai_matching_status: string; ai_matching_score?: number | null;
  ai_evidence_coverage?: number | null; new_status: string; override_direction: string;
  override_reason_code: string; note?: string | null;
}

interface Report {
  range: { date_from: string; date_to: string };
  scope: { global: boolean; positions: number };
  volume: { applications_received: number; positions_with_applications: number };
  funnel: { stage: string; count: number; rate_from_received: number | null; rate_from_previous: number | null }[];
  rejections: { screening: number; interview: number };
  time_to_shortlist: { applications: number; average_hours: number | null; median_hours: number | null };
  cv_processing: { operations: number; failed_operations: number; average_seconds: number | null };
  overrides: {
    decisions_with_ai: number; overrides: number; advanced_despite_ai: number; rejected_despite_ai: number;
    override_rate: number | null; by_reason: { code: string; label: string; count: number }[];
    cases: OverrideCase[]; tracking_since: string | null;
  };
  technical_errors: {
    files_uploaded: number; rejected_too_large: number; rejected_invalid_format: number; documents_needing_review: number;
    error_rate: number | null; by_file_type: { mime_type: string; total: number; needs_review: number }[];
    processing_error_codes: { error_code: string; count: number }[];
  };
  weekly: { week: string; applications: number; overrides: number }[];
}

const STAGE_LABELS: Record<string, string> = {
  IN_REVIEW: 'Đang xem', SHORTLIST: 'Shortlist', INTERVIEW: 'Đang phỏng vấn', OFFERED: 'Đã gửi đề nghị', ACCEPTED: 'Nhận việc',
};
const AI_LABELS: Record<string, string> = {
  MEETS_MANDATORY: 'Đáp ứng bắt buộc', NEEDS_HR_VERIFICATION: 'Cần HR xác minh', POSSIBLE_MISMATCH: 'Cần xem xét',
};
const DIRECTION_LABELS: Record<string, string> = {
  ADVANCED_DESPITE_AI: 'Đưa vào Shortlist dù AI chưa đạt', REJECTED_DESPITE_AI: 'Loại dù AI đánh giá đạt',
};
const FILE_TYPES: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
};

// One series per chart -> one brand hue, no legend; values are labelled directly.
const BAR_COLOR = '#0A2B57';

function isoDate(d: Date) { return d.toISOString().slice(0, 10); }
function pct(value: number | null | undefined) { return value == null ? '—' : `${Math.round(value * 1000) / 10}%`; }

function HorizontalBars({ rows, ariaLabel }: { rows: { label: string; value: number; hint?: string }[]; ariaLabel: string }) {
  const max = Math.max(1, ...rows.map(r => r.value));
  return (
    <Box role="list" aria-label={ariaLabel} sx={{ display: 'grid', gap: 1 }}>
      {rows.map(row => (
        <Tooltip key={row.label} title={row.hint || `${row.label}: ${row.value}`} placement="top" arrow>
          <Box role="listitem" sx={{ display: 'grid', gridTemplateColumns: 'minmax(120px, 34%) 1fr auto', alignItems: 'center', gap: 1.5, py: 0.5, cursor: 'default' }}>
            <Typography variant="body2" color="text.secondary" noWrap>{row.label}</Typography>
            <Box sx={{ height: 14, backgroundColor: 'action.hover', borderRadius: 1 }}>
              <Box sx={{ height: '100%', width: `${(row.value / max) * 100}%`, minWidth: row.value ? 4 : 0,
                backgroundColor: BAR_COLOR, borderRadius: '0 4px 4px 0' }} />
            </Box>
            <Typography variant="body2" fontWeight={600} sx={{ minWidth: 32, textAlign: 'right' }}>{row.value}</Typography>
          </Box>
        </Tooltip>
      ))}
    </Box>
  );
}

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography sx={{ fontSize: 26, fontWeight: 700, color: '#0A2B57', mt: 0.5 }}>{value}</Typography>
      {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
    </CardContent></Card>
  );
}

export default function ReportsPage() {
  const { t, dateLocale } = useI18n();
  const today = new Date();
  const [dateFrom, setDateFrom] = useState(isoDate(new Date(today.getTime() - 89 * 86400000)));
  const [dateTo, setDateTo] = useState(isoDate(today));
  const [positionId, setPositionId] = useState('');
  const [positions, setPositions] = useState<Position[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await analyticsApi.operations({ date_from: dateFrom, date_to: dateTo, position_id: positionId || undefined });
      setReport(res.data); setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải báo cáo vận hành"));
    } finally { setLoading(false); }
  }, [dateFrom, dateTo, positionId, t]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { positionsApi.listAll().then(setPositions).catch(() => setPositions([])); }, []);

  const hours = (h: number | null) => h == null ? '—' : h < 48 ? `${Math.round(h * 10) / 10} ${t("giờ")}` : `${Math.round(h / 24 * 10) / 10} ${t("ngày")}`;

  const exportCases = () => {
    if (!report) return;
    const header = ['Thời gian', 'Vị trí', 'Mã vị trí', 'Ứng viên', 'Kết luận AI', 'Điểm AI', 'Quyết định HR', 'Hướng điều chỉnh', 'Lý do', 'Ghi chú'];
    const reasonLabel = Object.fromEntries(report.overrides.by_reason.map(r => [r.code, r.label]));
    const rows = report.overrides.cases.map(c => [c.changed_at, c.position_title, c.position_code, c.candidate_name || '',
      AI_LABELS[c.ai_matching_status] || c.ai_matching_status, c.ai_matching_score ?? '', c.new_status,
      DIRECTION_LABELS[c.override_direction] || c.override_direction, reasonLabel[c.override_reason_code] || c.override_reason_code, c.note || '']);
    const csv = [header, ...rows].map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = `hr-override-${report.range.date_from}_${report.range.date_to}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Báo cáo vận hành")}</Typography>
        <Typography variant="body2" color="text.secondary">{t("Số liệu pilot để cải tiến quy trình và tiêu chí. Không dùng làm KPI hay xếp hạng cá nhân recruiter.")}</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <TextField size="small" type="date" label={t("Từ ngày")} value={dateFrom} InputLabelProps={{ shrink: true }} onChange={e => setDateFrom(e.target.value)} />
        <TextField size="small" type="date" label={t("Đến ngày")} value={dateTo} InputLabelProps={{ shrink: true }} onChange={e => setDateTo(e.target.value)} />
        <TextField size="small" select label={t("Vị trí")} value={positionId} sx={{ minWidth: 260 }} onChange={e => setPositionId(e.target.value)}>
          <MenuItem value="">{t("Tất cả vị trí trong phạm vi")}</MenuItem>
          {positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.title} · {p.position_code}</MenuItem>)}
        </TextField>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {loading && !report ? <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}><CircularProgress color="secondary" /></Box> : report && (<>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {report.scope.global ? t("Phạm vi: toàn bộ vị trí") : t("Phạm vi: {0} vị trí bạn phụ trách", report.scope.positions)}
          {loading && ' · '}{loading && t("Đang cập nhật…")}
        </Typography>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={3}><StatTile label={t("Hồ sơ nhận")} value={String(report.volume.applications_received)}
            sub={t("{0} vị trí có hồ sơ", report.volume.positions_with_applications)} /></Grid>
          <Grid item xs={6} md={3}><StatTile label={t("Từ lúc tải CV đến Shortlist")} value={hours(report.time_to_shortlist.median_hours)}
            sub={t("Trung vị · trung bình {0} · {1} hồ sơ", hours(report.time_to_shortlist.average_hours), report.time_to_shortlist.applications)} /></Grid>
          <Grid item xs={6} md={3}><StatTile label={t("Tỷ lệ HR điều chỉnh AI")} value={pct(report.overrides.override_rate)}
            sub={t("{0}/{1} quyết định sàng lọc có kết luận AI", report.overrides.overrides, report.overrides.decisions_with_ai)} /></Grid>
          <Grid item xs={6} md={3}><StatTile label={t("Tỷ lệ lỗi tệp")} value={pct(report.technical_errors.error_rate)}
            sub={t("{0} tệp tải lên", report.technical_errors.files_uploaded)} /></Grid>
        </Grid>

        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, mb: 0.5 }}>{t("Phễu tuyển dụng")}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>{t("Số hồ sơ nhận trong kỳ đã từng đạt mỗi vòng")}</Typography>
              <HorizontalBars ariaLabel={t("Phễu tuyển dụng")} rows={[
                { label: t("Hồ sơ nhận"), value: report.volume.applications_received },
                ...report.funnel.map(f => ({ label: t(STAGE_LABELS[f.stage] || f.stage), value: f.count,
                  hint: `${t(STAGE_LABELS[f.stage] || f.stage)}: ${f.count} · ${pct(f.rate_from_received)} ${t("so với hồ sơ nhận")} · ${pct(f.rate_from_previous)} ${t("so với vòng trước")}` })),
              ]} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                {t("Bị loại ở vòng sàng lọc: {0} · sau phỏng vấn: {1}", report.rejections.screening, report.rejections.interview)}
              </Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, mb: 0.5 }}>{t("Lý do HR điều chỉnh kết luận AI")}</Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                {t("Đưa vào Shortlist dù AI chưa đạt: {0} · Loại dù AI đánh giá đạt: {1}", report.overrides.advanced_despite_ai, report.overrides.rejected_despite_ai)}
              </Typography>
              <HorizontalBars ariaLabel={t("Lý do HR điều chỉnh kết luận AI")}
                rows={report.overrides.by_reason.map(r => ({ label: t(r.label), value: r.count }))} />
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                {report.overrides.tracking_since
                  ? t("Ghi nhận từ {0}; quyết định trước đó không có ảnh chụp kết luận AI nên không được tính.", new Date(report.overrides.tracking_since).toLocaleDateString(dateLocale))
                  : t("Chưa có quyết định nào được ghi nhận kèm kết luận AI.")}
              </Typography>
            </CardContent></Card>
          </Grid>
        </Grid>

        <Card variant="outlined" sx={{ mb: 3 }}><CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap', mb: 1 }}>
            <Typography variant="h4" sx={{ fontSize: 16 }}>{t("Các trường hợp HR điều chỉnh")} ({report.overrides.cases.length})</Typography>
            <Button size="small" startIcon={<DownloadIcon />} onClick={exportCases} disabled={!report.overrides.cases.length}>{t("Tải CSV")}</Button>
          </Box>
          <TableContainer>
            <Table size="small" aria-label={t("Các trường hợp HR điều chỉnh")}>
              <TableHead><TableRow>
                <TableCell>{t("Thời gian")}</TableCell><TableCell>{t("Vị trí")}</TableCell><TableCell>{t("Ứng viên")}</TableCell>
                <TableCell>{t("Kết luận AI")}</TableCell><TableCell>{t("Quyết định HR")}</TableCell><TableCell>{t("Lý do")}</TableCell>
              </TableRow></TableHead>
              <TableBody>
                {report.overrides.cases.length === 0 ? (
                  <TableRow><TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>{t("Không có trường hợp điều chỉnh trong kỳ")}</TableCell></TableRow>
                ) : report.overrides.cases.map(c => (
                  <TableRow key={c.event_id} hover>
                    <TableCell sx={{ whiteSpace: 'nowrap' }}>{new Date(c.changed_at).toLocaleDateString(dateLocale)}</TableCell>
                    <TableCell>{c.position_title}<Typography variant="caption" display="block" color="text.secondary">{c.position_code}</Typography></TableCell>
                    <TableCell>
                      <Button component={Link} size="small" sx={{ px: 0, textAlign: 'left' }}
                        href={`/positions/${c.position_id}/applicants/${c.application_id}`}>
                        {c.candidate_name || t("Ứng viên")}
                      </Button>
                    </TableCell>
                    <TableCell>{t(AI_LABELS[c.ai_matching_status] || c.ai_matching_status)}{c.ai_matching_score != null && ` · ${c.ai_matching_score}`}</TableCell>
                    <TableCell><Chip size="small" label={t(DIRECTION_LABELS[c.override_direction] || c.override_direction)} /></TableCell>
                    <TableCell>
                      {t(report.overrides.by_reason.find(r => r.code === c.override_reason_code)?.label || c.override_reason_code)}
                      {c.note && <Typography variant="caption" display="block" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>{c.note}</Typography>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent></Card>

        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, mb: 1.5 }}>{t("Lỗi kỹ thuật")}</Typography>
              <Table size="small" aria-label={t("Lỗi kỹ thuật")}><TableBody>
                <TableRow><TableCell>{t("Tệp bị từ chối do vượt dung lượng")}</TableCell><TableCell align="right">{report.technical_errors.rejected_too_large}</TableCell></TableRow>
                <TableRow><TableCell>{t("Tệp hỏng hoặc sai định dạng")}</TableCell><TableCell align="right">{report.technical_errors.rejected_invalid_format}</TableCell></TableRow>
                <TableRow><TableCell>{t("Tệp cần HR kiểm tra sau xử lý")}</TableCell><TableCell align="right">{report.technical_errors.documents_needing_review}</TableCell></TableRow>
                {report.technical_errors.by_file_type.map(f => (
                  <TableRow key={f.mime_type}><TableCell sx={{ pl: 4 }}>{FILE_TYPES[f.mime_type] || f.mime_type}</TableCell>
                    <TableCell align="right">{t("{0}/{1} cần kiểm tra", f.needs_review, f.total)}</TableCell></TableRow>
                ))}
                {report.technical_errors.processing_error_codes.map(e => (
                  <TableRow key={e.error_code}><TableCell sx={{ pl: 4 }}><Typography variant="caption" fontFamily="monospace">{e.error_code}</Typography></TableCell>
                    <TableCell align="right">{e.count}</TableCell></TableRow>
                ))}
                <TableRow><TableCell>{t("Lô xử lý CV thất bại")}</TableCell><TableCell align="right">{report.cv_processing.failed_operations}/{report.cv_processing.operations}</TableCell></TableRow>
                <TableRow><TableCell>{t("Thời gian xử lý trung bình một lô CV")}</TableCell>
                  <TableCell align="right">{report.cv_processing.average_seconds == null ? '—' : `${Math.round(report.cv_processing.average_seconds)} ${t("giây")}`}</TableCell></TableRow>
              </TableBody></Table>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{t("Hệ thống chưa đo được độ mờ của ảnh scan; tệp scan khó đọc được tính trong nhóm cần HR kiểm tra.")}</Typography>
            </CardContent></Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
              <Typography variant="h4" sx={{ fontSize: 16, mb: 1.5 }}>{t("Theo tuần")}</Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small" aria-label={t("Theo tuần")}>
                  <TableHead><TableRow><TableCell>{t("Tuần bắt đầu")}</TableCell><TableCell align="right">{t("Hồ sơ nhận")}</TableCell><TableCell align="right">{t("Lượt điều chỉnh AI")}</TableCell></TableRow></TableHead>
                  <TableBody>
                    {report.weekly.length === 0 ? (
                      <TableRow><TableCell colSpan={3} align="center" sx={{ color: 'text.secondary' }}>{t("Chưa có dữ liệu trong kỳ")}</TableCell></TableRow>
                    ) : report.weekly.map(w => (
                      <TableRow key={w.week}><TableCell>{new Date(w.week).toLocaleDateString(dateLocale)}</TableCell>
                        <TableCell align="right">{w.applications}</TableCell><TableCell align="right">{w.overrides}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent></Card>
          </Grid>
        </Grid>
      </>)}
    </Box>
  );
}
