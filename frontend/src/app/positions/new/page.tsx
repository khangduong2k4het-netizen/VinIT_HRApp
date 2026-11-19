'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Alert, Autocomplete, Box, Button, Card, CardContent, CircularProgress, Grid, MenuItem, Stack, TextField, Typography } from '@mui/material';
import apiClient, { criteriaApi, departmentsApi, positionsApi, rubricApi, usersApi } from '@/lib/api';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';
import CreatePositionProgressDialog, { type CreateProgressStep } from '@/components/positions/CreatePositionProgressDialog';
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
  // Tiến trình sau khi tạo: hộp thoại chặn màn hình, rồi tự sinh tiêu chí.
  const [progressStep, setProgressStep] = useState<CreateProgressStep | null>(null);
  const [progressError, setProgressError] = useState('');
  // Giữ id vị trí đã tạo để (a) không gửi lại request tạo, (b) mở đúng vị trí.
  const createdPositionId = useRef<string | null>(null);
  const navigating = useRef(false);
  const navTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tiếng Anh là mặc định (nền tảng quốc tế); tiếng Việt vẫn là tuỳ chọn được phép.
  const [language, setLanguage] = useState('en');
  // Validation appears once a field was visited, not on a pristine form.
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const touch = (field: string) => setTouched(current => current[field] ? current : { ...current, [field]: true });
  const pendingRequest = useRef<Record<string, unknown> | null>(null);
  const submitting = useRef(false);
  const selectedDepartment = departments.find(d => d.department_id === department);
  const preview = selectedDepartment?.code_format.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) => String(selectedDepartment.next_sequence).padStart((zeros || '').length || 1, '0')) || '';
  const dirty = !!(title || department || manager || content || url || file || family || deadline || language !== 'en');
  const missing = [
    !title.trim() ? t('Tên vị trí') : '',
    !department ? t('Đơn vị / Phòng ban') : '',
    !manager ? 'Hiring Manager' : '',
    !content.trim() ? t('Nội dung JD') : '',
  ].filter(Boolean);
  const titleError = touched.title && !title.trim() ? t('Nhập tên vị trí trước khi tạo.') : '';
  const departmentError = touched.department && !department ? t('Chọn đơn vị cho vị trí.') : '';
  const managerError = touched.manager && !manager ? t('Chọn Hiring Manager đang hoạt động.') : '';
  const contentError = touched.content && !content.trim() ? t('Dán, tải lên hoặc nhập JD trước khi tạo.') : '';
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
  useEffect(() => () => { if (navTimer.current) clearTimeout(navTimer.current); }, []);
  useUnsavedChangesGuard(dirty && !created && !createdPositionId.current && progressStep === null, t('Nội dung chưa lưu sẽ bị mất. Tiếp tục?'), { fallbackHref: '/positions' });

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
  /** Mở trang chi tiết đúng tab tiêu chí, để HR thấy ngay kết quả vừa sinh. */
  const openPosition = (positionId: string) => {
    // Vị trí đã được lưu nên nội dung form không còn là "việc chưa lưu": tắt
    // cảnh báo rời trang trước khi điều hướng, và chặn bấm hai lần sinh hai
    // lần chuyển trang.
    if (navigating.current) return;
    navigating.current = true;
    createdPositionId.current = null;
    setCreated(true);
    setProgressStep(null);
    router.push(`/positions/${positionId}?tab=criteria`);
  };

  /** Gọi sinh tiêu chí; trả về ``true`` khi thành công. */
  const runCriteriaGeneration = async (positionId: string) => {
    setProgressStep('generating'); setProgressError('');
    try {
      await criteriaApi.generateDraft(positionId);
      setProgressStep('done');
      // Ngắn để người dùng kịp thấy bước hoàn tất trước khi trang đổi. Giữ id
      // để dọn timer nếu trang bị gỡ trong 0,7 giây đó.
      navTimer.current = setTimeout(() => openPosition(positionId), 700);
      return true;
    } catch (err: any) {
      // Vị trí ĐÃ được tạo. Không được để người dùng tưởng thất bại rồi bấm
      // tạo lại — họ sẽ có hai vị trí trùng. Nói rõ vị trí đã lưu.
      setProgressError(err.response?.data?.detail
        || t('Không sinh được tiêu chí. Vị trí vẫn được lưu, không cần tạo lại.'));
      return false;
    }
  };

  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (submitting.current || importing || !department || !manager || !title.trim() || !content.trim()) return;
    // Nếu vị trí đã tạo ở lần bấm trước (ví dụ sinh tiêu chí lỗi rồi bấm lại),
    // không tạo thêm vị trí nữa — chỉ thử sinh lại tiêu chí.
    if (createdPositionId.current) { await runCriteriaGeneration(createdPositionId.current); return; }
    if (!pendingRequest.current) {
      pendingRequest.current = { ...(idempotencySupported ? { request_id: globalThis.crypto.randomUUID() } : {}),
        department_id: department, title: title.trim(), hiring_manager_user_id: manager.user_id,
        ...(family ? { job_family_id: family } : {}), jd_content: content.trim(), jd_language_code: language,
        application_deadline_at: deadline ? new Date(deadline).toISOString() : null };
    }
    submitting.current = true; setBusy(true); setError('');
    setProgressStep('creating'); setProgressError('');
    try {
      const res = await positionsApi.create(pendingRequest.current);
      setUncertain(false); pendingRequest.current = null;
      createdPositionId.current = res.data.position_id;
      // Sinh tiêu chí ngay, không bắt HR qua thêm bước thủ công.
      // Lỗi ở bước này không ném ra: vị trí đã tạo xong rồi.
      await runCriteriaGeneration(res.data.position_id);
    } catch (err: any) {
      const status = err.response?.status;
      setProgressStep(null);
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
          <Grid item xs={12} md={6}><TextField required fullWidth label={t('Tên vị trí')} value={title} onChange={e => setTitle(e.target.value)} onBlur={() => touch('title')} inputProps={{ maxLength: 200 }} error={!!titleError} helperText={titleError || undefined} /></Grid>
          <Grid item xs={12} md={6}><TextField required select fullWidth label={t('Đơn vị / Phòng ban')} value={department} onChange={e => setDepartment(e.target.value)} onBlur={() => touch('department')} error={!!departmentError} helperText={departmentError || undefined}>{departments.map(d => <MenuItem key={d.department_id} value={d.department_id}>{d.name}</MenuItem>)}</TextField></Grid>
          <Grid item xs={12} md={6}><Autocomplete options={managers} value={manager} onChange={(_, v) => setManager(v)} getOptionLabel={o => o.display_name || ''} isOptionEqualToValue={(a,b) => a.user_id === b.user_id} renderInput={params => <TextField {...params} required label="Hiring Manager" onBlur={() => touch('manager')} error={!!managerError} helperText={managerError || t('Chọn HM đang hoạt động, khác tài khoản HR.')} />} /></Grid>
          <Grid item xs={12} md={6}><TextField select fullWidth label={t('Nhóm vị trí (tùy chọn)')} value={family} onChange={e => setFamily(e.target.value)}><MenuItem value="">{t('Chưa chọn')}</MenuItem>{families.map(f => <MenuItem key={f.job_family_id} value={f.job_family_id}>{f.name}</MenuItem>)}</TextField></Grid>
          <Grid item xs={12} md={6}><TextField fullWidth label={t('Mã vị trí dự kiến (tự sinh)')} value={preview} InputProps={{ readOnly: true }} helperText={t('Mã chính thức do hệ thống cấp khi tạo.')} /></Grid>
          <Grid item xs={12} md={6}><TextField fullWidth type="datetime-local" label={t('Hạn ứng tuyển (giờ trình duyệt)')} value={deadline} onChange={e => setDeadline(e.target.value)} InputLabelProps={{ shrink: true }} /></Grid>
        </Grid>
        {deadline && <Alert severity="info" sx={{ mt: 2 }}>{t('Khi Careers được bật, vị trí đang mở còn hạn và JD mới nhất có thể được công khai, kể cả khi tiêu chí chưa duyệt.')}</Alert>}
      </CardContent></Card>
      <Card variant="outlined" sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ fontSize: 20, mb: 2 }}>{t('2. Mô tả công việc (JD)')}</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>{t('Chọn cách nhập, sau đó rà soát và chỉnh sửa nội dung trước khi tạo.')}</Typography>
        <TextField select label={t('Ngôn ngữ JD')} value={language} onChange={e => setLanguage(e.target.value)} sx={{ mb: 2, minWidth: 160 }} helperText={t('Mặc định là tiếng Anh; chọn Tiếng Việt nếu JD viết bằng tiếng Việt.')}><MenuItem value="en">English</MenuItem><MenuItem value="vi">Tiếng Việt</MenuItem></TextField>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
          {([['paste','Dán nội dung'],['file','Tải tệp DOCX / TXT'],['url','Nhập từ link']] as const).map(([key,label]) => <Button key={key} type="button" variant={source === key ? 'contained' : 'outlined'} onClick={() => { setSource(key); setError(''); }} aria-pressed={source === key}>{t(label)}</Button>)}
        </Stack>
        {source === 'file' && <Stack spacing={1} sx={{ mb: 2 }}><Typography variant="body2">{t('Chỉ hỗ trợ DOCX hoặc TXT UTF-8, tối đa 2 MB; không hỗ trợ DOC cũ.')}</Typography><input aria-label={t('Chọn tệp JD')} type="file" accept=".docx,.txt" onChange={e => setFile(e.target.files?.[0] || null)} /><Button type="button" variant="outlined" disabled={importing || !file} onClick={importJd}>{importing ? t('Đang đọc...') : t('Đọc tệp')}</Button></Stack>}
        {source === 'url' && <Stack spacing={1} sx={{ mb: 2 }}><TextField fullWidth label={t('Link JD')} value={url} onChange={e => setUrl(e.target.value)} helperText={t('Hỗ trợ link việc làm careerportalvinuni.talent.vn.')} /><Button type="button" variant="outlined" disabled={importing || !url.trim()} onClick={importJd}>{importing ? t('Đang đọc...') : t('Lấy nội dung JD')}</Button></Stack>}
        {warning && <Alert severity="info" sx={{ mb: 2 }}>{t(warning)}</Alert>}
        <TextField required fullWidth multiline minRows={12} label={t('Nội dung JD')} value={content} onChange={e => setContent(e.target.value)} onBlur={() => touch('content')} inputProps={{ maxLength: 100000 }} error={!!contentError} helperText={contentError || t('Bắt buộc: kiểm tra nội dung và yêu cầu công việc trước khi tạo.')} />
      </CardContent></Card>
      </Box>
      {missing.length > 0 && <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'right', mb: 1 }} data-testid="missing-fields">
        {t('Còn thiếu: {0}.', missing.join(', '))}
      </Typography>}
      <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mb: 4 }}><Button type="button" onClick={leave} disabled={busy}>{t('Hủy')}</Button><Button type="submit" variant="contained" color="secondary" disabled={busy || importing || uncertain || loadFailed || !department || !manager || !title.trim() || !content.trim()}>{busy ? t('Đang tạo...') : t('Tạo vị trí và tiếp tục')}</Button></Stack>
    </Box>}
    <CreatePositionProgressDialog
      open={progressStep !== null}
      step={progressStep ?? 'creating'}
      error={progressError}
      onRetryGenerate={() => { if (createdPositionId.current) void runCriteriaGeneration(createdPositionId.current); }}
      onEnterPosition={() => { if (createdPositionId.current) openPosition(createdPositionId.current); }}
    />
  </Box>;
}
