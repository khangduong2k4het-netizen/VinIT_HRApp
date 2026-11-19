'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Alert, Autocomplete, Box, Button, Card, CardContent, CircularProgress, Grid, MenuItem, Stack, TextField, Typography } from '@mui/material';
import apiClient, { departmentsApi, positionsApi, rubricApi, usersApi } from '@/lib/api';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';
import { useI18n } from '@/i18n/I18nProvider';
import type { Department, UserSummary } from '@/types';

type Source = 'paste' | 'file' | 'url';
export default function CreatePositionPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [managers, setManagers] = useState<UserSummary[]>([]);
  const [families, setFamilies] = useState<Array<{job_family_id: string; code: string; name: string}>>([]);
  const [department, setDepartment] = useState('');
  const [manager, setManager] = useState<UserSummary | null>(null);
  const [family, setFamily] = useState('');
  const [title, setTitle] = useState('');
  const [source, setSource] = useState<Source>('paste');
  const [content, setContent] = useState('');
  const [language, setLanguage] = useState('vi');
  const [deadline, setDeadline] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [created, setCreated] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const pendingRequest = useRef<Record<string, unknown> | null>(null);
  const submitting = useRef(false);
  const selectedDepartment = departments.find(d => d.department_id === department);
  const preview = selectedDepartment?.code_format.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) => String(selectedDepartment.next_sequence).padStart((zeros || '').length || 1, '0')) || '';
  const dirty = !!(title || department || manager || content || url || file || family || deadline || language !== 'vi');
  // Server-side idempotency needs a UUID; fall back to the server's duplicate check.
  const idempotencySupported = typeof globalThis.crypto?.randomUUID === 'function';

  useEffect(() => {
    let active = true;
    Promise.all([departmentsApi.list(false), usersApi.list({ role: 'HIRING_MANAGER' }), rubricApi.families()])
      .then(([d, h, f]) => { if (active) { setDepartments(d.data || []); setManagers(h.data || []); setFamilies(f.data || []); } })
      .catch(() => { if (active) { setLoadFailed(true); setError(t('Không thể tải phòng ban hoặc Hiring Manager. Vui lòng tải lại trang.')); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [t]);
  useUnsavedChangesGuard(dirty && !created, t('Nội dung chưa lưu sẽ bị mất. Tiếp tục?'), { fallbackHref: '/positions' });

  const importJd = async () => {
    if (content.trim() && !window.confirm(t('Nội dung JD hiện tại sẽ được thay bằng nội dung mới. Tiếp tục?'))) return;
    if (source === 'file' && !file) { setError(t('Hãy chọn tệp DOCX hoặc TXT.')); return; }
    if (source === 'url' && !url.trim()) { setError(t('Hãy nhập link JD.')); return; }
    setImporting(true); setError(''); setWarning('');
    try {
      const data = new FormData();
      if (file) data.append('file', file);
      const res = source === 'file'
        ? await apiClient.post('/jd-import/file', data, { headers: { 'Content-Type': 'multipart/form-data' } })
        : await apiClient.post('/jd-import/url', { url: url.trim() });
      setContent(res.data.content); setWarning(res.data.warning);
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể lấy JD. Vui lòng thử lại hoặc dán nội dung.')); }
    finally { setImporting(false); }
  };
  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (submitting.current || importing || !department || !manager || !title.trim() || !content.trim()) return;
    if (!pendingRequest.current) {
      pendingRequest.current = { ...(idempotencySupported ? { request_id: globalThis.crypto.randomUUID() } : {}),
        department_id: department, title: title.trim(), hiring_manager_user_id: manager.user_id,
        ...(family ? { job_family_id: family } : {}), jd_content: content.trim(), jd_language_code: language,
        application_deadline_at: deadline ? new Date(deadline).toISOString() : null };
    }
    submitting.current = true; setBusy(true); setError('');
    try {
      const res = await positionsApi.create(pendingRequest.current);
      setCreated(true); setUncertain(false); pendingRequest.current = null;
      router.push(`/positions/${res.data.position_id}?tab=criteria`);
    } catch (err: any) {
      const status = err.response?.status;
      if (!status || status >= 500 || uncertain) {
        setUncertain(true);
        setError(t('Kết quả tạo chưa rõ. Có thể thử lại cùng yêu cầu an toàn hoặc kiểm tra danh sách; không sửa nội dung khi đang đối soát.'));
      } else { pendingRequest.current = null; setError(err.response?.data?.detail || t('Không thể tạo vị trí. Vui lòng kiểm tra lại.')); }
    } finally { submitting.current = false; setBusy(false); }
  };
  const leave = () => router.push('/positions');
  return <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
    <Button onClick={leave} sx={{ mb: 1 }}>← {t('Vị trí tuyển dụng')}</Button>
    <Typography variant="h1" sx={{ fontSize: 28, mb: 1 }}>{t('Tạo vị trí tuyển dụng')}</Typography>
    <Typography color="text.secondary" sx={{ mb: 3 }}>{t('Nhập thông tin và JD, sau đó rà soát tiêu chí cùng Hiring Manager.')}</Typography>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={uncertain ? <Button component={Link} href="/positions" color="inherit">{t('Kiểm tra danh sách')}</Button> : undefined}>{t(error)}{uncertain && <Button onClick={() => submit()} disabled={busy} sx={{ ml: 1 }}>{t('Thử lại cùng yêu cầu')}</Button>}</Alert>}
    {loading ? <CircularProgress /> : <Box component="form" onSubmit={submit}>
      <Box component="fieldset" disabled={uncertain || busy} sx={{ border: 0, p: 0, m: 0, minWidth: 0 }}><Card variant="outlined" sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ fontSize: 20, mb: 2 }}>{t('1. Thông tin vị trí')}</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}><TextField required fullWidth label={t('Tên vị trí')} value={title} onChange={e => setTitle(e.target.value)} inputProps={{ maxLength: 200 }} /></Grid>
          <Grid item xs={12} md={6}><TextField required select fullWidth label={t('Đơn vị / Phòng ban')} value={department} onChange={e => setDepartment(e.target.value)}>{departments.map(d => <MenuItem key={d.department_id} value={d.department_id}>{d.name}</MenuItem>)}</TextField></Grid>
          <Grid item xs={12} md={6}><Autocomplete options={managers} value={manager} onChange={(_, v) => setManager(v)} getOptionLabel={o => o.display_name || ''} isOptionEqualToValue={(a,b) => a.user_id === b.user_id} renderInput={params => <TextField {...params} required label="Hiring Manager" helperText={t('Chọn HM đang hoạt động, khác tài khoản HR.')} />} /></Grid>
          <Grid item xs={12} md={6}><TextField select fullWidth label={t('Nhóm vị trí (tùy chọn)')} value={family} onChange={e => setFamily(e.target.value)}><MenuItem value="">{t('Chưa chọn')}</MenuItem>{families.map(f => <MenuItem key={f.job_family_id} value={f.job_family_id}>{f.name}</MenuItem>)}</TextField></Grid>
          <Grid item xs={12} md={6}><TextField fullWidth label={t('Mã vị trí dự kiến (tự sinh)')} value={preview} InputProps={{ readOnly: true }} helperText={t('Mã chính thức do hệ thống cấp khi tạo.')} /></Grid>
          <Grid item xs={12} md={6}><TextField fullWidth type="datetime-local" label={t('Hạn ứng tuyển (giờ trình duyệt)')} value={deadline} onChange={e => setDeadline(e.target.value)} InputLabelProps={{ shrink: true }} /></Grid>
        </Grid>
        {deadline && <Alert severity="info" sx={{ mt: 2 }}>{t('Khi Careers được bật, vị trí đang mở còn hạn và JD mới nhất có thể được công khai, kể cả khi tiêu chí chưa duyệt.')}</Alert>}
      </CardContent></Card>
      <Card variant="outlined" sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ fontSize: 20, mb: 2 }}>{t('2. Mô tả công việc (JD)')}</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>{t('Chọn cách nhập, sau đó rà soát và chỉnh sửa nội dung trước khi tạo.')}</Typography>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
          {([['paste','Dán nội dung'],['file','Tải tệp DOCX / TXT'],['url','Nhập từ link']] as const).map(([key,label]) => <Button key={key} type="button" variant={source === key ? 'contained' : 'outlined'} onClick={() => { setSource(key); setError(''); }} aria-pressed={source === key}>{t(label)}</Button>)}
        </Stack>
        {source === 'file' && <Stack spacing={1} sx={{ mb: 2 }}><Typography variant="body2">{t('Chỉ hỗ trợ DOCX hoặc TXT UTF-8, tối đa 2 MB; không hỗ trợ DOC cũ.')}</Typography><input aria-label={t('Chọn tệp JD')} type="file" accept=".docx,.txt" onChange={e => setFile(e.target.files?.[0] || null)} /><Button type="button" variant="outlined" disabled={importing || !file} onClick={importJd}>{importing ? t('Đang đọc...') : t('Đọc tệp')}</Button></Stack>}
        {source === 'url' && <Stack spacing={1} sx={{ mb: 2 }}><TextField fullWidth label={t('Link JD')} value={url} onChange={e => setUrl(e.target.value)} helperText={t('Hỗ trợ link việc làm careerportalvinuni.talent.vn.')} /><Button type="button" variant="outlined" disabled={importing || !url.trim()} onClick={importJd}>{importing ? t('Đang đọc...') : t('Lấy nội dung JD')}</Button></Stack>}
        {warning && <Alert severity="info" sx={{ mb: 2 }}>{t(warning)}</Alert>}
        <TextField select label={t('Ngôn ngữ JD')} value={language} onChange={e => setLanguage(e.target.value)} sx={{ mb: 2, minWidth: 160 }}><MenuItem value="vi">Tiếng Việt</MenuItem><MenuItem value="en">English</MenuItem></TextField>
        <TextField required fullWidth multiline minRows={12} label={t('Nội dung JD')} value={content} onChange={e => setContent(e.target.value)} inputProps={{ maxLength: 100000 }} helperText={t('Bắt buộc: kiểm tra nội dung và yêu cầu công việc trước khi tạo.')} />
      </CardContent></Card>
      </Box><Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mb: 4 }}><Button type="button" onClick={leave} disabled={busy}>{t('Hủy')}</Button><Button type="submit" variant="contained" color="secondary" disabled={busy || importing || uncertain || loadFailed || !department || !manager || !title.trim() || !content.trim()}>{busy ? t('Đang tạo...') : t('Tạo vị trí và tiếp tục')}</Button></Stack>
    </Box>}
  </Box>;
}
