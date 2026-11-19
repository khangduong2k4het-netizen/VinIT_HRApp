'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, MenuItem, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import { authApi, positionsApi, qualityApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { REVIEW_LABELS } from '@/lib/reviewLabels';

type Case = { inspection_id: string; position_id: string; position_title: string; candidate_name: string;
  reasons: string[]; status: string; revision: number; assigned_to: string | null; reviewer_name: string | null };
type Evidence = { evidence_id: string; quote: string; page_number: number | null; verification_status: string };
type Finding = { result_id: string; name: string; category: string; outcome: string; evidence: Evidence[] };
type Flag = { category: string; criterion_result_id?: string; note: string };
type Detail = { case: Case; assessment: { matching_status: string; evidence_coverage: number; assessment_id: string; profile_version_id: string };
  findings: Finding[]; facts: { fact_type: string; fact_value: unknown; source_page_number: number | null }[]; flags: Flag[] };
const categories = ['INCORRECT_EVIDENCE', 'MISSING_CONTENT', 'INCORRECT_FACT', 'OCR_ERROR', 'INCORRECT_MATCH'];

function Inspection({ id, onChanged }: { id: string; onChanged: () => void }) {
  const { t } = useI18n();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [source, setSource] = useState('');
  const [mime, setMime] = useState('');
  const [text, setText] = useState('');
  const [sourceError, setSourceError] = useState(false);
  const [textError, setTextError] = useState(false);
  const [exactText, setExactText] = useState(true);
  const [ocrConfidence, setOcrConfidence] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [verdict, setVerdict] = useState('CORRECT');
  const [flags, setFlags] = useState<Flag[]>([]);
  const [userId, setUserId] = useState('');
  useEffect(() => {
    let active = true;
    let blob: string | null = null;
    qualityApi.detail(id).then(r => { if (active) setDetail(r.data); }).catch(() => { if (active) setError(t('Không thể tải kiểm định')); });
    authApi.me().then(r => { if (active) setUserId(r.data.user_id); }).catch(() => {});
    qualityApi.source(id).then(r => {
      if (!active) return;
      blob = URL.createObjectURL(r.data); setSource(blob!); setMime(r.data.type);
    }).catch(() => { if (active) setSourceError(true); });
    qualityApi.text(id).then(r => { if (active) { setText(r.data.text); setExactText(r.data.exact_snapshot); setOcrConfidence(r.data.ocr_mean_confidence); } }).catch(() => { if (active) setTextError(true); });
    return () => { active = false; if (blob) URL.revokeObjectURL(blob); };
  }, [id, t]);
  const action = async (submit: boolean) => {
    if (!detail || busy) return;
    setBusy(true); setError('');
    try {
      if (submit) await qualityApi.submit(id, { expected_revision: detail.case.revision, verdict,
        flags: verdict === 'ISSUES_FOUND' ? flags : [] });
      else await qualityApi.claim(id, detail.case.revision);
      setDetail((await qualityApi.detail(id)).data); onChanged();
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể lưu kiểm định')); }
    finally { setBusy(false); }
  };
  const exportFeedback = async () => {
    setBusy(true);
    try {
      const result = await qualityApi.feedback(id);
      const url = URL.createObjectURL(new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = `quality-feedback-${id}.json`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError(t('Không thể xuất phản hồi kiểm định')); }
    finally { setBusy(false); }
  };
  if (!detail) return <Box sx={{ my: 2 }}>{error ? <Alert severity="error">{error}</Alert> : <CircularProgress />}</Box>;
  const mine = detail.case.status === 'IN_REVIEW' && detail.case.assigned_to === userId;
  const sections = text.split(/--- Page (\d+) ---/);
  const pageIndex = sections.findIndex((value, index) => index % 2 === 1 && Number(value) === page);
  const pageText = pageIndex >= 0 ? sections[pageIndex + 1] : text;
  return <Card sx={{ mt: 3 }}><CardContent>
    <Typography variant="h6">{t('Đối soát CV, văn bản và bằng chứng')}</Typography>
    <Alert severity="info" sx={{ my: 2 }}>{t('Kiểm định gắn với bản đánh giá đã chọn. Phản hồi không tự sửa kết quả AI hoặc trạng thái tuyển dụng.')}</Alert>
    {error && <Alert severity="error">{error}</Alert>}
    <Chip label={t(REVIEW_LABELS[detail.case.status] || detail.case.status)} sx={{ mb: 2 }} />
    {detail.case.status === 'PENDING' && <Button disabled={busy} onClick={() => action(false)}>{t('Nhận kiểm định')}</Button>}
    <TextField type="number" size="small" label={t('Trang nguồn')} value={page} inputProps={{ min: 1 }}
      onChange={e => setPage(Math.max(1, Number(e.target.value) || 1))} sx={{ ml: 2, mb: 2, width: 120 }} />
    <Grid container spacing={2}>
      <Grid item xs={12} md={6}>
        {sourceError && <Alert severity="warning">{t('Chưa thể đọc CV nguồn. Có thể thử lại sau.')}</Alert>}
        {source && (mime.includes('pdf') ? <iframe title={t('CV gốc để kiểm định')} src={`${source}#page=${page}`} style={{ width: '100%', height: 650, border: 0 }} />
          : mime.startsWith('image/')
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={source} alt={t('CV gốc để kiểm định')} style={{ maxWidth: '100%', display: 'block' }} />
            : <Button component="a" href={source} download="source.docx">{t('Tải tài liệu nguồn để đối soát')}</Button>)}
      </Grid>
      <Grid item xs={12} md={6}>
        <Typography variant="subtitle1">{t('Văn bản trích xuất')}</Typography>
        {!textError && !exactText && <Alert severity="warning">{t('Bản cũ chưa lưu liên kết văn bản chính xác; văn bản dưới đây được đối chiếu theo thời điểm xử lý.')}</Alert>}
        {ocrConfidence !== null && <Typography variant="caption">{t('Độ tin cậy OCR trung bình: {0}%', ocrConfidence)}</Typography>}
        {textError ? <Alert severity="warning">{t('Chưa có văn bản trích xuất cho bản đánh giá này')}</Alert>
          : <Box component="pre" sx={{ whiteSpace: 'pre-wrap', maxHeight: 260, overflow: 'auto', bgcolor: '#f5f5f5', p: 2 }}>{pageText}</Box>}
        <Typography variant="subtitle1">{t('Thông tin đã trích xuất')}</Typography>
        {detail.facts.map((fact, index) => <Typography key={index} variant="body2" sx={{ mb: 1 }}>{t(REVIEW_LABELS[fact.fact_type] || fact.fact_type)}: {JSON.stringify(fact.fact_value)}</Typography>)}
        <Typography variant="subtitle1" sx={{ mt: 2 }}>{t('Đánh giá theo tiêu chí')}</Typography>
        {detail.findings.map(finding => <Box key={finding.result_id} sx={{ borderTop: '1px solid #ddd', py: 1 }}>
          <Typography>{finding.name} · {t(REVIEW_LABELS[finding.outcome] || finding.outcome)}</Typography>
          {finding.evidence.map(e => <Box key={e.evidence_id} sx={{ my: 1 }}>
            <Typography variant="body2">{e.quote}</Typography>
            <Chip size="small" label={t(REVIEW_LABELS[e.verification_status] || e.verification_status)} />
            {e.page_number && <Button size="small" onClick={() => setPage(e.page_number!)}>{t('Trang {0}', e.page_number)}</Button>}
          </Box>)}
        </Box>)}
      </Grid>
    </Grid>
    {detail.case.status === 'COMPLETED' && <Box sx={{ mt: 2 }}>
      <Typography>{t('Phản hồi đã ghi nhận')}</Typography>
      <Button disabled={busy} onClick={exportFeedback}>{t('Tải phản hồi cho đội kỹ thuật')}</Button>
      {detail.flags.map((flag, index) => <Alert key={index} severity="warning" sx={{ my: 1 }}>{t(REVIEW_LABELS[flag.category] || flag.category)}: {flag.note}</Alert>)}
    </Box>}
    {mine && <Box sx={{ mt: 3 }}>
      <TextField select label={t('Kết luận kiểm định')} value={verdict} onChange={e => setVerdict(e.target.value)} sx={{ minWidth: 220 }}>
        <MenuItem value="CORRECT">{t('Không phát hiện lỗi')}</MenuItem><MenuItem value="ISSUES_FOUND">{t('Có lỗi cần xử lý')}</MenuItem>
      </TextField>
      {verdict === 'ISSUES_FOUND' && <>
        {flags.map((flag, index) => <Box key={index} sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
          <TextField select label={t('Loại lỗi')} value={flag.category} sx={{ minWidth: 180 }} onChange={e => setFlags(old => old.map((v, n) => n === index ? { ...v, category: e.target.value } : v))}>
            {categories.map(c => <MenuItem key={c} value={c}>{t(REVIEW_LABELS[c] || c)}</MenuItem>)}
          </TextField>
          <TextField select label={t('Tiêu chí liên quan')} value={flag.criterion_result_id || ''} sx={{ minWidth: 180 }} onChange={e => setFlags(old => old.map((v, n) => n === index ? { ...v, criterion_result_id: e.target.value || undefined } : v))}>
            <MenuItem value="">{t('Toàn bộ hồ sơ')}</MenuItem>{detail.findings.map(f => <MenuItem key={f.result_id} value={f.result_id}>{f.name}</MenuItem>)}
          </TextField>
          <TextField multiline label={t('Mô tả lỗi và đề nghị xử lý')} value={flag.note} inputProps={{ maxLength: 2000 }} sx={{ flex: 1, minWidth: 220 }}
            onChange={e => setFlags(old => old.map((v, n) => n === index ? { ...v, note: e.target.value } : v))} />
          <Button onClick={() => setFlags(old => old.filter((_, n) => n !== index))}>{t('Bỏ phản hồi')}</Button>
        </Box>)}
        <Button disabled={flags.length >= 100} onClick={() => setFlags(old => [...old, { category: 'INCORRECT_EVIDENCE', note: '' }])}>{t('Thêm phản hồi lỗi')}</Button>
      </>}
      <Button variant="contained" disabled={busy || sourceError || textError || !source || !text ||
        (verdict === 'ISSUES_FOUND' && (!flags.length || flags.some(f => !f.note.trim())))} onClick={() => action(true)} sx={{ ml: 2 }}>{t('Nộp kết quả kiểm định')}</Button>
    </Box>}
  </CardContent></Card>;
}

export default function QualityPage() {
  const { t } = useI18n();
  const [cases, setCases] = useState<Case[]>([]);
  const [positions, setPositions] = useState<{ position_id: string; title: string }[]>([]);
  const [position, setPosition] = useState('');
  const [status, setStatus] = useState('PENDING');
  const [selected, setSelected] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const load = useCallback(async () => {
    try { setCases((await qualityApi.list({ position_id: position || undefined, status: status || undefined, offset })).data); setError(''); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải danh sách kiểm định')); setCases([]); }
  }, [position, status, offset, t]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { positionsApi.listAll().then(setPositions).catch(() => {}); }, []);
  const sample = async () => {
    if (!position || busy) return;
    setBusy(true);
    try { const r = await qualityApi.sample(position); setNotice(t('Đã tạo {0} mẫu kiểm định.', r.data.created_count)); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tạo mẫu kiểm định')); }
    finally { setBusy(false); }
  };
  return <>
    <Typography variant="h4" sx={{ mb: 2 }}>{t('Kiểm định chất lượng')}</Typography>
    <Typography color="text.secondary" sx={{ mb: 2 }}>{t('Dành cho HR Lead: mẫu ngẫu nhiên 10%, cộng hồ sơ có một tiêu chí bắt buộc chưa đáp ứng hoặc độ phủ 65–75%.')}</Typography>
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
      <TextField select label={t('Vị trí tuyển dụng')} value={position} sx={{ minWidth: 250 }} onChange={e => { setPosition(e.target.value); setOffset(0); setSelected(''); }}>
        <MenuItem value="">{t('Tất cả vị trí')}</MenuItem>{positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.title}</MenuItem>)}
      </TextField>
      <TextField select label={t('Trạng thái')} value={status} sx={{ minWidth: 180 }} onChange={e => { setStatus(e.target.value); setOffset(0); }}>
        <MenuItem value="">{t('Tất cả')}</MenuItem>{['PENDING', 'IN_REVIEW', 'COMPLETED'].map(s => <MenuItem key={s} value={s}>{t(REVIEW_LABELS[s] || s)}</MenuItem>)}
      </TextField>
      <Button disabled={!position || busy} onClick={sample}>{t('Bổ sung mẫu kiểm định')}</Button><Button onClick={load}>{t('Tải lại')}</Button>
    </Box>
    {error && <Alert severity="error">{error}</Alert>}{notice && <Alert severity="success">{notice}</Alert>}
    <Box sx={{ overflowX: 'auto' }}><Table><TableHead><TableRow>
      {['Ứng viên', 'Vị trí tuyển dụng', 'Lý do chọn mẫu', 'Trạng thái', 'Người kiểm định', 'Thao tác'].map(h => <TableCell key={h}>{t(h)}</TableCell>)}
    </TableRow></TableHead><TableBody>
      {cases.map(c => <TableRow key={c.inspection_id} selected={selected === c.inspection_id}>
        <TableCell>{c.candidate_name || '—'}</TableCell><TableCell>{c.position_title}</TableCell>
        <TableCell>{c.reasons.map(r => <Chip key={r} size="small" label={t(REVIEW_LABELS[r] || r)} sx={{ m: 0.25 }} />)}</TableCell>
        <TableCell>{t(REVIEW_LABELS[c.status] || c.status)}</TableCell><TableCell>{c.reviewer_name || '—'}</TableCell>
        <TableCell><Button onClick={() => setSelected(c.inspection_id)}>{t('Mở kiểm định')}</Button></TableCell>
      </TableRow>)}
      {!cases.length && <TableRow><TableCell colSpan={6}>{t('Chưa có mẫu kiểm định trong bộ lọc này.')}</TableCell></TableRow>}
    </TableBody></Table></Box>
    <Box sx={{ mt: 2 }}><Button disabled={!offset} onClick={() => setOffset(n => Math.max(0, n - 50))}>{t('Trang trước')}</Button>
      <Button disabled={cases.length < 50} onClick={() => setOffset(n => n + 50)}>{t('Trang sau')}</Button></Box>
    {selected && <Inspection key={selected} id={selected} onChanged={load} />}
  </>;
}
