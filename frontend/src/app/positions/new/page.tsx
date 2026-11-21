'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Alert, Autocomplete, Box, Button, Card, CardContent, CircularProgress, Grid, MenuItem, Stack, TextField, Typography } from '@mui/material';
import apiClient, { criteriaApi, departmentsApi, positionsApi, rubricApi, usersApi } from '@/lib/api';
import { useUnsavedChangesGuard } from '@/hooks/useUnsavedChangesGuard';
import CreatePositionProgressDialog, { type CreateProgressStep } from '@/components/positions/CreatePositionProgressDialog';
import { interpretGenerationFailure } from '@/lib/criteriaGeneration';
import { EMPLOYMENT_TYPES } from '@/lib/employmentTypes';
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
  // Loại việc làm là thứ trang /careers dùng để lọc và để dựng thanh danh mục.
  // Thiếu ô này thì cột employment_type luôn NULL và mọi bộ lọc loại việc làm
  // trên trang tuyển dụng đều rỗng — không phải lỗi giao diện Careers mà là
  // không có chỗ nào nhập dữ liệu.
  const [employmentType, setEmploymentType] = useState('');
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
  // Nguồn bộ tiêu chí đầu tiên. Mặc định 'ai' để luồng cũ không đổi; 'template'
  // thì bỏ hẳn bước sinh AI và áp rubric mẫu ngay, tránh vòng duyệt vô nghĩa:
  // một bộ DRAFT của AI chặn apply_template bằng 409 cho tới khi được duyệt.
  const [criteriaSource, setCriteriaSource] = useState<'ai' | 'template'>('ai');
  const [templateVersions, setTemplateVersions] = useState<Array<{template_version_id: string; title: string; family_name: string; job_family_id: string; version_number: number; level_band: string | null}>>([]);
  const [templateId, setTemplateId] = useState('');
  const [templatesLoading, setTemplatesLoading] = useState(false);
  // Đã hỏi thư viện chưa — tách khỏi `templateVersions.length` vì thư viện
  // RỖNG (0 rubric đã xuất bản) cũng là một câu trả lời hợp lệ. Dùng độ dài
  // làm điều kiện dừng thì effect tự kích lại mỗi lần và gọi API vô hạn.
  const templatesLoaded = useRef(false);
  // Giữ id vị trí đã tạo để (a) không gửi lại request tạo, (b) mở đúng vị trí.
  const createdPositionId = useRef<string | null>(null);
  const navigating = useRef(false);
  const navTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Tiếng Anh là mặc định (nền tảng quốc tế); tiếng Việt vẫn là tuỳ chọn được phép.
  // Validation appears once a field was visited, not on a pristine form.
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const touch = (field: string) => setTouched(current => current[field] ? current : { ...current, [field]: true });
  const pendingRequest = useRef<Record<string, unknown> | null>(null);
  const submitting = useRef(false);
  const selectedDepartment = departments.find(d => d.department_id === department);
  const preview = selectedDepartment?.code_format.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) => String(selectedDepartment.next_sequence).padStart((zeros || '').length || 1, '0')) || '';
  const dirty = !!(title || department || manager || content || url || file || family || deadline);
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
  useUnsavedChangesGuard(dirty && !created && !createdPositionId.current, t('Nội dung chưa lưu sẽ bị mất. Tiếp tục?'), { fallbackHref: '/positions' });

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
  // Chú ý: cảnh báo chỉ tắt khi vị trí đã tồn tại. Trong lúc đang gửi yêu cầu
  // tạo (`progressStep === 'creating'`) thì vẫn còn, vì đóng tab lúc đó có thể
  // mất nội dung mà chưa biết vị trí đã được tạo hay chưa.
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

  /** Hỏi server xem vị trí đã có bản tiêu chí nào chưa; ``null`` nếu không hỏi được. */
  const criteriaExist = async (positionId: string): Promise<boolean | null> => {
    try {
      const res = await criteriaApi.listVersions(positionId);
      return Array.isArray(res.data) && res.data.length > 0;
    } catch { return null; }
  };

  /** Mở vị trí sau khi tiêu chí đã sẵn sàng trong DB. */
  const finishCriteria = (positionId: string) => {
    setProgressStep('done'); setProgressError('');
    // Ngắn để người dùng kịp thấy bước hoàn tất trước khi trang đổi. Giữ id
    // để dọn timer nếu trang bị gỡ trong 0,7 giây đó.
    navTimer.current = setTimeout(() => openPosition(positionId), 700);
  };

  /** Gọi sinh tiêu chí; trả về ``true`` khi tiêu chí đã có trên server. */
  const runCriteriaGeneration = async (positionId: string) => {
    setProgressStep('generating'); setProgressError('');
    try {
      await criteriaApi.generateDraft(positionId);
      finishCriteria(positionId);
      return true;
    } catch (err: any) {
      // Vị trí ĐÃ được tạo, nên không bao giờ được khuyên tạo lại. Câu "chưa
      // tạo được tiêu chí" chỉ được nói khi đã KIỂM CHỨNG là chưa có.
      // Response không có `detail` thường là request bị cắt ở proxy chứ không
      // phải backend từ chối — lúc đó phải hỏi lại server.
      const exists = await criteriaExist(positionId);
      const outcome = interpretGenerationFailure(err, exists);
      if (outcome.action === 'verified') { finishCriteria(positionId); return true; }
      if (outcome.action === 'unknown') {
        setProgressError(t('Chưa xác nhận được tiêu chí đã tạo hay chưa (lỗi kết nối). Mở vị trí để xem kết quả; không cần tạo lại vị trí.'));
        return false;
      }
      setProgressError(outcome.detail
        || t('Yêu cầu tạo tiêu chí bị ngắt trước khi có kết quả và hệ thống chưa lưu tiêu chí nào. Vị trí đã được lưu, không cần tạo lại.'));
      return false;
    }
  };

  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (submitting.current || importing || !department || !manager || !title.trim() || !content.trim()) return;
    // Nếu vị trí đã tạo ở lần bấm trước (ví dụ sinh tiêu chí lỗi rồi bấm lại),
    // không tạo thêm vị trí nữa — chỉ thử sinh lại tiêu chí.
    if (createdPositionId.current) {
      if (criteriaSource === 'template' && templateId) await runTemplateApply(createdPositionId.current);
      else await runCriteriaGeneration(createdPositionId.current);
      return;
    }
    if (!pendingRequest.current) {
      pendingRequest.current = { ...(idempotencySupported ? { request_id: globalThis.crypto.randomUUID() } : {}),
        department_id: department, title: title.trim(), hiring_manager_user_id: manager.user_id,
        ...(family ? { job_family_id: family } : {}),
        ...(employmentType ? { employment_type: employmentType } : {}), jd_content: content.trim(),
        application_deadline_at: deadline ? new Date(deadline).toISOString() : null };
    }
    submitting.current = true; setBusy(true); setError('');
    setProgressStep('creating'); setProgressError('');
    try {
      const res = await positionsApi.create(pendingRequest.current);
      setUncertain(false); pendingRequest.current = null;
      createdPositionId.current = res.data.position_id;
      // Sinh tiêu chí ngay, không bắt HR qua thêm bước thủ công. Lỗi ở bước
      // này không ném ra: vị trí đã tạo xong rồi.
      if (criteriaSource === 'template' && templateId) await runTemplateApply(res.data.position_id);
      else await runCriteriaGeneration(res.data.position_id);
    } catch (err: any) {
      const status = err.response?.status;
      setProgressStep(null);
      if (!status || status >= 500 || uncertain) {
        setUncertain(true);
        setError(t('Kết quả tạo chưa rõ. Có thể thử lại cùng yêu cầu an toàn hoặc kiểm tra danh sách; không sửa nội dung khi đang đối soát.'));
      } else { pendingRequest.current = null; setError(err.response?.data?.detail || t('Không thể tạo vị trí. Vui lòng kiểm tra lại.')); }
    } finally { submitting.current = false; setBusy(false); }
  };
  // Chỉ tải khi người dùng thực sự chọn rubric mẫu: HR tạo vị trí bằng AI
  // không phải chờ một request thư viện không dùng tới.
  useEffect(() => {
    if (criteriaSource !== 'template' || templatesLoaded.current) return;
    templatesLoaded.current = true;
    setTemplatesLoading(true);
    rubricApi.templates()
      .then(res => setTemplateVersions((Array.isArray(res.data) ? res.data : []).filter((v: any) => v.status === 'PUBLISHED')))
      .catch(() => setTemplateVersions([]))
      .finally(() => setTemplatesLoading(false));
  }, [criteriaSource]);

  /** Áp rubric mẫu lên vị trí vừa tạo; ``true`` khi bộ tiêu chí đã có trên server. */
  const runTemplateApply = async (positionId: string): Promise<boolean> => {
    setProgressStep('generating'); setProgressError('');
    try {
      await rubricApi.apply(positionId, templateId);
      finishCriteria(positionId);
      return true;
    } catch (err: any) {
      // Vị trí đã tạo xong. Áp thất bại thì để HR mở vị trí và thử lại, không
      // khuyên tạo lại vị trí.
      const exists = await criteriaExist(positionId);
      setProgressStep('generating');
      setProgressError(err?.response?.data?.detail
        || (exists === false
          ? t('Chưa áp được rubric mẫu và vị trí chưa có bộ tiêu chí nào. Mở vị trí để áp lại khi sẵn sàng.')
          : t('Chưa xác nhận được rubric mẫu đã áp hay chưa. Mở vị trí để xem kết quả; không cần tạo lại vị trí.')));
      return false;
    }
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
          <Grid item xs={12} md={6}><TextField select fullWidth label={t('Loại việc làm (tùy chọn)')} value={employmentType} onChange={e => setEmploymentType(e.target.value)} helperText={t('Dùng để lọc trên trang tuyển dụng. Bỏ trống thì tin vẫn đăng, chỉ không nằm trong bộ lọc nào.')}>
            <MenuItem value="">{t('Chưa chọn')}</MenuItem>
            {EMPLOYMENT_TYPES.map(value => <MenuItem key={value} value={value}>{t(value)}</MenuItem>)}
          </TextField></Grid>
        </Grid>
        {deadline && <Alert severity="info" sx={{ mt: 2 }}>{t('Khi Careers được bật, vị trí đang mở còn hạn và JD mới nhất có thể được công khai, kể cả khi tiêu chí chưa duyệt.')}</Alert>}
      </CardContent></Card>
      <Card variant="outlined" sx={{ mb: 2 }}><CardContent><Typography variant="h2" sx={{ fontSize: 20, mb: 2 }}>{t('2. Mô tả công việc (JD)')}</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>{t('Chọn cách nhập, sau đó rà soát và chỉnh sửa nội dung trước khi tạo.')}</Typography>
        {/* Không còn ô chọn ngôn ngữ JD. Ngôn ngữ được suy ra từ nội dung ở
            máy chủ (app/services/language_detect.py) — ô cũ không ảnh hưởng gì
            tới kết quả, nên để lại chỉ khiến HR tin nhầm là nó có tác dụng. */}
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
          {([['paste','Dán nội dung'],['file','Tải tệp DOCX / TXT'],['url','Nhập từ link']] as const).map(([key,label]) => <Button key={key} type="button" variant={source === key ? 'contained' : 'outlined'} onClick={() => { setSource(key); setError(''); }} aria-pressed={source === key}>{t(label)}</Button>)}
        </Stack>
        {source === 'file' && <Stack spacing={1} sx={{ mb: 2 }}><Typography variant="body2">{t('Chỉ hỗ trợ DOCX hoặc TXT UTF-8, tối đa 2 MB; không hỗ trợ DOC cũ.')}</Typography><input aria-label={t('Chọn tệp JD')} type="file" accept=".docx,.txt" onChange={e => setFile(e.target.files?.[0] || null)} /><Button type="button" variant="outlined" disabled={importing || !file} onClick={importJd}>{importing ? t('Đang đọc...') : t('Đọc tệp')}</Button></Stack>}
        {source === 'url' && <Stack spacing={1} sx={{ mb: 2 }}><TextField fullWidth label={t('Link JD')} value={url} onChange={e => setUrl(e.target.value)} helperText={t('Hỗ trợ link việc làm careerportalvinuni.talent.vn.')} /><Button type="button" variant="outlined" disabled={importing || !url.trim()} onClick={importJd}>{importing ? t('Đang đọc...') : t('Lấy nội dung JD')}</Button></Stack>}
        {warning && <Alert severity={warning.startsWith('Tệp được trích xuất nhưng CHƯA được quét') ? 'warning' : 'info'} sx={{ mb: 2 }} data-testid="jd-import-warning">{t(warning)}</Alert>}
        <TextField required fullWidth multiline minRows={12} label={t('Nội dung JD')} value={content} onChange={e => setContent(e.target.value)} onBlur={() => touch('content')} inputProps={{ maxLength: 100000 }} error={!!contentError} helperText={contentError || t('Bắt buộc: kiểm tra nội dung và yêu cầu công việc trước khi tạo.')} />
      </CardContent></Card>
      <Card variant="outlined" sx={{ mb: 2 }}><CardContent>
        <Typography variant="h2" sx={{ fontSize: 20, mb: 1 }}>{t('3. Bộ tiêu chí đầu tiên')}</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {t('Chọn trước khi tạo: hệ thống tạo bộ tiêu chí nào cho vị trí này. Cả hai đều ra bản nháp và đều cần HR và Hiring Manager duyệt trước khi chấm ứng viên.')}
        </Typography>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
          <Button type="button" variant={criteriaSource === 'ai' ? 'contained' : 'outlined'}
            onClick={() => { setCriteriaSource('ai'); setError(''); }} aria-pressed={criteriaSource === 'ai'}>
            {t('AI sinh từ JD')}
          </Button>
          <Button type="button" variant={criteriaSource === 'template' ? 'contained' : 'outlined'}
            onClick={() => { setCriteriaSource('template'); setError(''); }} aria-pressed={criteriaSource === 'template'}>
            {t('Dùng rubric mẫu đã xuất bản')}
          </Button>
        </Stack>
        {criteriaSource === 'ai' ? (
          <Alert severity="info">
            {t('AI đọc JD của vị trí này rồi đề xuất tiêu chí và trọng số. Bám sát JD nhất, nhưng trọng số có thể khác nhau giữa các vị trí cùng loại.')}
          </Alert>
        ) : templatesLoading ? <CircularProgress size={24} /> : !templateVersions.length ? (
          <Alert severity="warning">
            {t('Thư viện chưa có rubric mẫu nào đã xuất bản. Vào mục Rubric để tạo và xuất bản trước, hoặc chọn AI sinh từ JD.')}
          </Alert>
        ) : <>
          <TextField select fullWidth label={t('Rubric mẫu')} value={templateId}
            onChange={e => setTemplateId(e.target.value)}
            helperText={t('Rubric cùng nhóm vị trí được xếp lên đầu. Dùng rubric khác nhóm là lựa chọn có chủ ý, không phải mặc định.')}>
            {[...templateVersions]
              .sort((a, b) => Number(b.job_family_id === family) - Number(a.job_family_id === family))
              .map(v => <MenuItem key={v.template_version_id} value={v.template_version_id}>
                {v.title} · {v.family_name} · v{v.version_number}{v.level_band ? ` · ${v.level_band}` : ''}
                {family && v.job_family_id !== family && <Typography component="span" variant="caption" sx={{ ml: 1, color: '#B42318' }}>{t('(khác nhóm vị trí)')}</Typography>}
              </MenuItem>)}
          </TextField>
          {!family && <Alert severity="info" sx={{ mt: 2 }}>
            {t('Chưa chọn Nhóm vị trí nên thư viện không lọc được theo nhóm. Nên chọn nhóm ở bước 1 để tránh áp nhầm rubric của nhóm khác.')}
          </Alert>}
        </>}
      </CardContent></Card>
      </Box>
      {missing.length > 0 && <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'right', mb: 1 }} data-testid="missing-fields">
        {t('Còn thiếu: {0}.', missing.join(', '))}
      </Typography>}
      <Stack direction="row" spacing={2} justifyContent="flex-end" sx={{ mb: 4 }}><Button type="button" onClick={leave} disabled={busy}>{t('Hủy')}</Button><Button type="submit" variant="contained" color="secondary" disabled={busy || importing || uncertain || loadFailed || !department || !manager || !title.trim() || !content.trim() || (criteriaSource === 'template' && !templateId)}>{busy ? t('Đang tạo...') : t('Tạo vị trí và tiếp tục')}</Button></Stack>
    </Box>}
    <CreatePositionProgressDialog
      open={progressStep !== null}
      step={progressStep ?? 'creating'}
      error={progressError}
      onRetryGenerate={() => {
        if (!createdPositionId.current) return;
        if (criteriaSource === 'template' && templateId) void runTemplateApply(createdPositionId.current);
        else void runCriteriaGeneration(createdPositionId.current);
      }}
      onEnterPosition={() => { if (createdPositionId.current) openPosition(createdPositionId.current); }}
    />
  </Box>;
}
