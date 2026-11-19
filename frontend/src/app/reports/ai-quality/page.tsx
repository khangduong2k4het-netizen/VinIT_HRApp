'use client';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, MenuItem, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from '@mui/material';
import { analyticsApi, authApi, departmentsApi, positionsApi, rubricApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import PageHeader from '@/components/common/PageHeader';
import RateTrendChart from '@/components/reports/RateTrendChart';
import { chartPoints, counts, localIsoDate, markerKindKey, pct, trendStatement,
  type BreakdownRow, type Marker, type Proportion, type Trends } from '@/lib/aiQuality';

const REASONS: Record<string, string> = {
  SYNONYM_TERMS: 'Từ đồng nghĩa', EQUIVALENT_CREDENTIAL: 'Chứng chỉ tương đương', IMPLICIT_EVIDENCE: 'Bằng chứng ngầm định',
  INTERVIEW_VERIFICATION: 'Xác minh qua phỏng vấn', EXTRACTION_ERROR: 'Lỗi trích xuất', CRITERIA_MISFIT: 'Tiêu chí chưa phù hợp', OTHER: 'Khác',
};
const FLAGS: Record<string, string> = {
  INCORRECT_EVIDENCE: 'Bằng chứng sai', MISSING_CONTENT: 'Thiếu nội dung', INCORRECT_FACT: 'Dữ kiện sai', OCR_ERROR: 'Lỗi OCR', INCORRECT_MATCH: 'Kết luận so khớp sai',
};
const MARKER_KINDS: Record<string, string> = { MATCHING_POLICY: 'Chính sách chấm điểm', PROMPT: 'Prompt', RULES: 'Bộ quy tắc', MANUAL: 'Ghi chú của Admin' };
const CRITERION_TYPES: Record<string, string> = { MUST_HAVE: 'Tiêu chí bắt buộc', NICE_TO_HAVE: 'Tiêu chí ưu tiên', UNKNOWN: 'Khác' };
const FILE_TYPES: Record<string, string> = { PDF: 'PDF', DOCX: 'DOCX', IMAGE: 'Ảnh (JPG/PNG)', OTHER: 'Khác' };

function Rate({ p }: { p: Proportion }) {
  const { t } = useI18n();
  if (p.insufficient) return <Typography variant="body2" color="text.secondary">{counts(p)} · {t('chưa đủ dữ liệu')}</Typography>;
  return <Typography variant="body2"><b>{pct(p.rate)}</b> ({counts(p)}) <Box component="span" sx={{ color: 'text.secondary' }}>[{pct(p.ci_low)}–{pct(p.ci_high)}]</Box></Typography>;
}

export default function AiQualityPage() {
  const { t } = useI18n();
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 179);
    return localIsoDate(d);
  });
  const [dateTo, setDateTo] = useState(() => localIsoDate(new Date()));
  const [grain, setGrain] = useState<'week' | 'month'>('week');
  const [departmentId, setDepartmentId] = useState('');
  const [jobFamilyId, setJobFamilyId] = useState('');
  const [positionId, setPositionId] = useState('');
  const [departmentsList, setDepartmentsList] = useState<{ department_id: string; name: string }[]>([]);
  const [jobFamiliesList, setJobFamiliesList] = useState<{ job_family_id: string; code: string; name: string }[]>([]);
  const [positionsList, setPositionsList] = useState<{ position_id: string; position_code: string; title: string }[]>([]);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [markers, setMarkers] = useState<Marker[]>([]);
  const [reasons, setReasons] = useState<BreakdownRow[]>([]);
  const [flags, setFlags] = useState<BreakdownRow[]>([]);
  const [families, setFamilies] = useState<BreakdownRow[]>([]);
  const [departments, setDepartments] = useState<BreakdownRow[]>([]);
  const [versions, setVersions] = useState<BreakdownRow[]>([]);
  const [fileTypes, setFileTypes] = useState<BreakdownRow[]>([]);
  const [criterionTypes, setCriterionTypes] = useState<BreakdownRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [canExportGoldenSet, setCanExportGoldenSet] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState('');
  const [markerDate, setMarkerDate] = useState(() => localIsoDate(new Date()));
  const [markerTitle, setMarkerTitle] = useState('');
  const [markerNote, setMarkerNote] = useState('');
  const [markerBusy, setMarkerBusy] = useState(false);
  const [markerError, setMarkerError] = useState('');

  const buildFilterParams = useCallback(() => ({
    date_from: dateFrom,
    date_to: dateTo,
    ...(departmentId ? { department_id: departmentId } : {}),
    ...(jobFamilyId ? { job_family_id: jobFamilyId } : {}),
    ...(positionId ? { position_id: positionId } : {}),
  }), [dateFrom, dateTo, departmentId, jobFamilyId, positionId]);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    const range = buildFilterParams();
    try {
      const [tr, mk, rs, fl, fa, dp, ve, ft, ct] = await Promise.all([
        analyticsApi.qualityTrends({ ...range, grain }),
        analyticsApi.qualityMarkers({ date_from: dateFrom, date_to: dateTo }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'override_reason' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'flag_category' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'job_family' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'department' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'matching_policy_version' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'file_type' }),
        analyticsApi.qualityBreakdown({ ...range, dimension: 'criterion_type' }),
      ]);
      setTrends(tr.data); setMarkers(mk.data.markers); setReasons(rs.data.rows); setFlags(fl.data.rows);
      setFamilies(fa.data.rows); setDepartments(dp.data.rows); setVersions(ve.data.rows);
      setFileTypes(ft.data.rows); setCriterionTypes(ct.data.rows);
    } catch (err: any) {
      setTrends(null);
      setError(err.response?.status === 403 ? t('Bạn không có quyền xem chất lượng AI.') : err.response?.status === 400
        ? t('Khoảng thời gian không hợp lệ.') : t('Không thể tải dữ liệu chất lượng AI.'));
    } finally { setLoading(false); }
  }, [buildFilterParams, dateFrom, dateTo, grain, t]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    authApi.me().then(r => {
      const roles: string[] = r.data.system_roles || [];
      setIsAdmin(roles.includes('ADMIN'));
      setCanExportGoldenSet(roles.includes('ADMIN') || roles.includes('HR_LEAD'));
    }).catch(() => {});
    departmentsApi.list().then(r => setDepartmentsList(r.data || [])).catch(() => {});
    rubricApi.listFamilies().then(r => setJobFamiliesList(r.data || [])).catch(() => {});
    positionsApi.listAll().then(list => setPositionsList(list || [])).catch(() => {});
  }, []);

  const exportGoldenSet = async (format: 'json' | 'csv') => {
    setExportBusy(true); setExportError('');
    try {
      const res = await analyticsApi.exportGoldenSet({ ...buildFilterParams(), format });
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hra-golden-set-${dateFrom}-${dateTo}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError(t('Không thể xuất tập nhãn ẩn danh.'));
    } finally {
      setExportBusy(false);
    }
  };

  const addMarker = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!markerTitle.trim() || markerBusy) return;
    setMarkerBusy(true); setMarkerError('');
    try {
      await analyticsApi.createQualityMarker({ occurred_on: markerDate, title: markerTitle.trim(), note: markerNote.trim() || undefined });
      setMarkerTitle(''); setMarkerNote('');
      await load();
    } catch { setMarkerError(t('Không thể lưu mốc thay đổi.')); } finally { setMarkerBusy(false); }
  };

  const series = trends?.series || [];
  const minSample = trends?.min_sample ?? 20;
  const statement = (pick: Parameters<typeof chartPoints>[1], neutral = false) => {
    const s = trendStatement(chartPoints(series, pick));
    if (neutral) {
      return s === 'BETTER' ? t('Mức bất đồng đang giảm (khoảng tin cậy không chồng nhau).')
        : s === 'WORSE' ? t('Mức bất đồng đang tăng (khoảng tin cậy không chồng nhau).')
        : s === 'NO_CLEAR_CHANGE' ? t('Chưa thấy thay đổi rõ rệt.') : t('Chưa đủ dữ liệu để nói về xu hướng.');
    }
    return s === 'BETTER' ? t('Đang cải thiện (khoảng tin cậy không chồng nhau).') : s === 'WORSE' ? t('Đang xấu đi (khoảng tin cậy không chồng nhau).')
      : s === 'NO_CLEAR_CHANGE' ? t('Chưa thấy thay đổi rõ rệt.') : t('Chưa đủ dữ liệu để nói về xu hướng.');
  };
  const cards: { title: string; hint: string; neutral?: boolean; pick: Parameters<typeof chartPoints>[1] }[] = [
    { title: t('Tỷ lệ HR ghi đè kết quả AI'), hint: t('Đo mức bất đồng của HR với AI, không phải độ đúng.'), neutral: true, pick: r => r.overrides },
    { title: t('Tỷ lệ lỗi — mẫu ngẫu nhiên'), hint: t('Ước lượng tỷ lệ lỗi chung của AI. Chỉ tính ca kiểm định lấy ngẫu nhiên.'), pick: r => r.qa_random_sample },
    { title: t('Tỷ lệ lỗi — nhóm rủi ro'), hint: t('Nhóm được chọn vì nghi ngờ nên tỷ lệ cao là bình thường. Không dùng làm tỷ lệ lỗi chung.'), pick: r => r.qa_risk_group },
  ];

  return (
    <Box>
      <PageHeader eyebrow={t('Báo cáo')} title={t('Chất lượng AI')}
        description={t('Số liệu tổng hợp theo thời gian. Không chia theo từng nhà tuyển dụng; ô có ít hơn {0} ca chỉ hiện số đếm, không hiện tỷ lệ.', minSample)} />
      <Card sx={{ mb: 2 }}><CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" type="date" label={t('Từ ngày')} value={dateFrom} onChange={e => setDateFrom(e.target.value)} InputLabelProps={{ shrink: true }} /></Grid>
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" type="date" label={t('Đến ngày')} value={dateTo} onChange={e => setDateTo(e.target.value)} InputLabelProps={{ shrink: true }} /></Grid>
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" select label={t('Theo')} value={grain} onChange={e => setGrain(e.target.value as 'week' | 'month')}>
            <MenuItem value="week">{t('Tuần')}</MenuItem><MenuItem value="month">{t('Tháng')}</MenuItem></TextField></Grid>
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" select label={t('Phòng ban')} value={departmentId} onChange={e => setDepartmentId(e.target.value)}>
            <MenuItem value="">{t('Tất cả')}</MenuItem>
            {departmentsList.map(d => <MenuItem key={d.department_id} value={d.department_id}>{d.name}</MenuItem>)}
          </TextField></Grid>
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" select label={t('Khối ngành')} value={jobFamilyId} onChange={e => setJobFamilyId(e.target.value)}>
            <MenuItem value="">{t('Tất cả')}</MenuItem>
            {jobFamiliesList.map(f => <MenuItem key={f.job_family_id} value={f.job_family_id}>{f.code} · {f.name}</MenuItem>)}
          </TextField></Grid>
          <Grid item xs={12} sm={4} md={2}><TextField fullWidth size="small" select label={t('Vị trí')} value={positionId} onChange={e => setPositionId(e.target.value)}>
            <MenuItem value="">{t('Tất cả')}</MenuItem>
            {positionsList.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}
          </TextField></Grid>
        </Grid>
        {canExportGoldenSet && (
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
            <Button size="small" variant="outlined" disabled={exportBusy} onClick={() => exportGoldenSet('json')}>
              {t('Xuất tập nhãn ẩn danh (JSON)')}
            </Button>
            <Button size="small" variant="outlined" disabled={exportBusy} onClick={() => exportGoldenSet('csv')}>
              {t('Xuất tập nhãn ẩn danh (CSV)')}
            </Button>
            <Typography variant="caption" color="text.secondary">
              {t('Chỉ HR Lead/Admin. Không chứa họ tên, email, SĐT; mỗi lần xuất được ghi audit.')}
            </Typography>
          </Stack>
        )}
        {exportError && <Alert severity="error" sx={{ mt: 1.5 }}>{exportError}</Alert>}
      </CardContent></Card>
      {loading && <CircularProgress aria-label={t('Đang tải')} />}
      {error && <Alert severity="error" action={<Button color="inherit" onClick={load}>{t('Thử lại')}</Button>}>{error}</Alert>}
      {!loading && trends && (
        <>
          {series.length === 0 && <Alert severity="info" sx={{ mb: 2 }}>{t('Chưa có dữ liệu trong khoảng thời gian này.')}</Alert>}
          <Grid container spacing={2}>
            {cards.map(card => (
              <Grid item xs={12} md={6} key={card.title}><Card sx={{ height: '100%' }}><CardContent>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>{card.title}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{card.hint}</Typography>
                <RateTrendChart points={chartPoints(series, card.pick)} markers={markers} grain={trends.range.grain} ariaLabel={card.title} />
                <Typography variant="body2" sx={{ mt: 1, fontWeight: 600 }}>{statement(card.pick, card.neutral)}</Typography>
              </CardContent></Card></Grid>
            ))}
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>{t('Hàng đợi kiểm định')}</Typography>
              <Typography variant="h3" sx={{ mt: 1 }}>{trends.qa_backlog.open_cases}</Typography>
              <Typography variant="body2" color="text.secondary">
                {trends.qa_backlog.oldest_created_at ? t('Ca cũ nhất tạo ngày {0}', trends.qa_backlog.oldest_created_at.slice(0, 10)) : t('Không có ca tồn đọng.')}
              </Typography>
            </CardContent></Card></Grid>
          </Grid>

          <Card sx={{ mt: 2 }}><CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo kỳ')}</Typography>
            <TableContainer><Table size="small" aria-label={t('Chi tiết theo kỳ')}>
              <TableHead><TableRow>
                <TableCell>{t('Kỳ bắt đầu')}</TableCell><TableCell>{t('Ghi đè')}</TableCell><TableCell>{t('Lỗi — mẫu ngẫu nhiên')}</TableCell>
                <TableCell>{t('Lỗi — nhóm rủi ro')}</TableCell><TableCell>{t('Tiêu chí chưa rõ')}</TableCell><TableCell>{t('Cần HR xác minh')}</TableCell><TableCell>{t('Độ phủ bằng chứng TB')}</TableCell>
              </TableRow></TableHead>
              <TableBody>{series.map(r => (
                <TableRow key={r.period}>
                  <TableCell>{r.period}</TableCell><TableCell><Rate p={r.overrides} /></TableCell><TableCell><Rate p={r.qa_random_sample} /></TableCell>
                  <TableCell><Rate p={r.qa_risk_group} /></TableCell><TableCell><Rate p={r.assessments.unclear_criteria} /></TableCell>
                  <TableCell><Rate p={r.assessments.needs_verification} /></TableCell><TableCell>{pct(r.assessments.average_evidence_coverage)}</TableCell>
                </TableRow>))}</TableBody>
            </Table></TableContainer>
          </CardContent></Card>

          <Grid container spacing={2} sx={{ mt: 0 }}>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Lý do ghi đè')}</Typography>
              {reasons.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : reasons.map(r => (
                <Box key={String(r.key)} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography variant="body2">{t(REASONS[String(r.key)] || 'Khác')}</Typography>
                  <Typography variant="body2"><b>{r.count}</b>{r.share != null ? ` · ${pct(r.share)}` : ''}</Typography>
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Loại lỗi kiểm định')}</Typography>
              {flags.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : flags.map(r => (
                <Box key={String(r.key)} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography variant="body2">{t(FLAGS[String(r.key)] || 'Khác')}</Typography>
                  <Typography variant="body2"><b>{r.count}</b>{r.share != null ? ` · ${pct(r.share)}` : ''}</Typography>
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo khối ngành')}</Typography>
              {families.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : families.map(r => (
                <Box key={String(r.key)} sx={{ py: 0.75 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.label || t('Chưa phân loại')}</Typography>
                  <Typography variant="caption" color="text.secondary" component="div">{t('Ghi đè')}</Typography>{r.overrides && <Rate p={r.overrides} />}
                  <Typography variant="caption" color="text.secondary" component="div">{t('Lỗi — mẫu ngẫu nhiên')}</Typography>{r.qa_random_sample && <Rate p={r.qa_random_sample} />}
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo phòng ban')}</Typography>
              {departments.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : departments.map(r => (
                <Box key={String(r.key)} sx={{ py: 0.75 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.label || t('Chưa phân loại')}</Typography>
                  <Typography variant="caption" color="text.secondary" component="div">{t('Ghi đè')}</Typography>{r.overrides && <Rate p={r.overrides} />}
                  <Typography variant="caption" color="text.secondary" component="div">{t('Lỗi — mẫu ngẫu nhiên')}</Typography>{r.qa_random_sample && <Rate p={r.qa_random_sample} />}
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo loại tệp (lỗi xử lý)')}</Typography>
              {fileTypes.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : fileTypes.map(r => (
                <Box key={String(r.key)} sx={{ py: 0.75 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{t(FILE_TYPES[String(r.key)] || 'Khác')} · {r.completed} {t('tệp')}</Typography>
                  {r.needs_verification && <Rate p={r.needs_verification} />}
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo loại tiêu chí (tỷ lệ chưa rõ)')}</Typography>
              {criterionTypes.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : criterionTypes.map(r => (
                <Box key={String(r.key)} sx={{ py: 0.75 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{t(CRITERION_TYPES[String(r.key)] || 'Khác')} · {r.completed} {t('kết quả')}</Typography>
                  {r.needs_verification && <Rate p={r.needs_verification} />}
                </Box>))}
            </CardContent></Card></Grid>
            <Grid item xs={12} md={6}><Card sx={{ height: '100%' }}><CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Theo phiên bản chính sách chấm điểm')}</Typography>
              {versions.length === 0 ? <Typography color="text.secondary">{t('Chưa có dữ liệu.')}</Typography> : versions.map(r => (
                <Box key={String(r.key)} sx={{ py: 0.75 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{r.key} · {r.completed} {t('đánh giá')}</Typography>
                  {r.qa_random_sample && <Rate p={r.qa_random_sample} />}
                </Box>))}
            </CardContent></Card></Grid>
          </Grid>

          <Card sx={{ mt: 2 }}><CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>{t('Mốc thay đổi')}</Typography>
            {markers.length === 0 ? <Typography color="text.secondary">{t('Chưa có mốc thay đổi trong khoảng này.')}</Typography> : markers.map((m, i) => {
              const kindKey = markerKindKey(m);
              return (
                <Box key={`${m.date}-${i}`} sx={{ display: 'flex', gap: 1.5, alignItems: 'baseline', py: 0.5, flexWrap: 'wrap' }}>
                  <Typography variant="body2" sx={{ minWidth: 92 }}>{m.date}</Typography>
                  <Chip size="small" label={t(MARKER_KINDS[kindKey] || kindKey)} />
                  <Typography variant="body2">{m.title}{m.note ? ` — ${m.note}` : ''}</Typography>
                </Box>
              );
            })}
            {isAdmin && (
              <Box component="form" onSubmit={addMarker} sx={{ mt: 2, display: 'grid', gap: 1.5, maxWidth: 560 }}>
                <Typography variant="subtitle2">{t('Thêm mốc thay đổi (chỉ Admin)')}</Typography>
                <TextField size="small" type="date" label={t('Ngày')} value={markerDate} onChange={e => setMarkerDate(e.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField size="small" label={t('Tiêu đề')} value={markerTitle} onChange={e => setMarkerTitle(e.target.value)} inputProps={{ maxLength: 200 }} required />
                <TextField size="small" label={t('Ghi chú')} value={markerNote} onChange={e => setMarkerNote(e.target.value)} inputProps={{ maxLength: 1000 }} multiline minRows={2} />
                {markerError && <Alert severity="error">{markerError}</Alert>}
                <Button type="submit" variant="contained" disabled={markerBusy || !markerTitle.trim()} sx={{ justifySelf: 'start' }}>{t('Lưu mốc')}</Button>
              </Box>)}
          </CardContent></Card>
        </>
      )}
    </Box>
  );
}
