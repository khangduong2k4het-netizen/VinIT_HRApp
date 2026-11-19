'use client';

import { useCallback, useEffect, useState } from 'react';
import { careersFailure } from '@/lib/syntheticIntake';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container, FormControlLabel, Stack, TextField, Typography } from '@mui/material';

type Job = { position_id: string; position_code: string; title: string; org_unit: string | null; work_location: string | null; work_mode: string | null; employment_type: string | null; application_deadline_at: string; description: string | null; can_apply_test: boolean };
type JobPage = { items: Job[]; next_cursor: string | null };

export default function CareersPage() {
  const { t, dateLocale } = useI18n();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState('');
  const [poolToken, setPoolToken] = useState('');
  const [optedIn, setOptedIn] = useState(false);
  const [savedToken, setSavedToken] = useState('');
  const [success, setSuccess] = useState('');
  // Tên tệp đã chọn, để người nộp bằng điện thoại thấy mình đã chọn đúng CV.
  const [cvName, setCvName] = useState('');
  const load = useCallback(async (next: string | null, signal?: AbortSignal) => {
    setLoading(true); setError('');
    try {
      const query = next ? `?cursor=${encodeURIComponent(next)}` : '';
      const res = await fetch(`/v1/careers/jobs${query}`, { cache: 'no-store', signal });
      if (!res.ok) throw new Error('Không thể tải danh sách vị trí. Vui lòng thử lại sau.');
      const page: JobPage = await res.json();
      setJobs(previous => next ? [...previous, ...page.items.filter(item => !previous.some(existing => existing.position_id === item.position_id))] : page.items);
      setCursor(page.next_cursor);
    } catch (err) {
      if (!signal?.aborted) setError(err instanceof Error ? err.message : 'Không thể tải danh sách vị trí.');
    } finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void load(null, controller.signal);
    return () => controller.abort();
  }, [load]);
  const selectJob = (selected: Job) => {
    if (!globalThis.crypto?.randomUUID || !globalThis.crypto?.getRandomValues) {
      setError('Trình duyệt không hỗ trợ tạo mã an toàn; cần HTTPS.'); return;
    }
    setRequestId(crypto.randomUUID());
    setPoolToken(Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join(''));
    setJob(selected); setOptedIn(false); setSavedToken(''); setError(''); setSuccess(''); setCvName('');
  };
  const apply = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!job || busy) return;
    // required trên input tệp ẩn làm trình duyệt báo lỗi không thể focus, nên kiểm tra ở đây.
    const form = event.currentTarget;
    const file = (form.elements.namedItem('cv') as HTMLInputElement | null)?.files?.[0];
    if (!file) { setError('Hãy chọn tệp CV trước khi gửi hồ sơ.'); return; }
    setBusy(true); setError(''); setSuccess('');
    try {
      const data = new FormData(form);
      data.set('request_id', requestId);
      data.set('pool_opt_in', optedIn ? 'true' : 'false');
      data.set('pool_token', optedIn ? poolToken : '');
      const res = await fetch(`/v1/careers/jobs/${job.position_id}/apply`, { method: 'POST', body: data, cache: 'no-store' });
      if (!res.ok) {
        const result = await res.json().catch(() => ({}));
        setError(careersFailure(res.status, result.detail));
        return;
      }
      setSuccess('Đã tiếp nhận yêu cầu thử nghiệm; CV vẫn cần được xử lý. Gửi lại cùng yêu cầu không tạo thêm hồ sơ.'); setSavedToken(optedIn ? poolToken : ''); setJob(null); setCvName('');
    } catch { setError(careersFailure(null, null)); }
    finally { setBusy(false); }
  };
  return <Container maxWidth="md" sx={{ py: { xs: 2.5, md: 5 } }}>
    <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2} sx={{ mb: 2 }}>
      <Typography variant="h1" sx={{ fontSize: { xs: 24, md: 30 }, lineHeight: 1.2 }}>{t('Vị trí đang tuyển dụng')}</Typography>
      <LanguageSwitcher />
    </Stack>
    <Alert severity="warning" sx={{ mb: 3 }}>{t('Chỉ kiểm thử với CV và thông tin tổng hợp, email dạng @example.test. Không gửi thông tin cá nhân hoặc CV thật.')}</Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={!job ? <Button color="inherit" onClick={() => void load(cursor)}>{t('Thử lại')}</Button> : undefined}>{t(error)}</Alert>}
    {success && <Alert severity="success" sx={{ mb: 2 }}>{t(success)}</Alert>}
    {savedToken && <Alert severity="info" sx={{ mb: 2 }}>
      <Typography variant="body2">{t('Mã rút lựa chọn thử nghiệm:')} <Box component="code" sx={{ overflowWrap: 'anywhere' }}>{savedToken}</Box></Typography>
      <Typography variant="body2">{t('Lưu mã và dùng tại /pool-withdraw.')}</Typography>
    </Alert>}
    {!loading && !error && !jobs.length && <Typography>{t('Hiện chưa có vị trí còn hạn.')}</Typography>}
    <Stack spacing={2}>{jobs.map(item => <Card variant="outlined" key={item.position_id}><CardContent>
      <Typography variant="h2" sx={{ fontSize: { xs: 19, md: 21 }, lineHeight: 1.3 }}>{item.title}</Typography>
      <Typography variant="body2" sx={{ mt: 0.5 }}>{[item.position_code, item.org_unit, item.work_location, item.work_mode, item.employment_type].filter(Boolean).join(' · ')}</Typography>
      <Typography variant="body2">{t('Hạn: {0}', new Date(item.application_deadline_at).toLocaleString(dateLocale))}</Typography>
      {item.description ? <Typography component="p" sx={{ whiteSpace: 'pre-wrap', my: 2 }}>{item.description}</Typography> : <Typography sx={{ my: 2 }}>{t('Chưa có mô tả công việc.')}</Typography>}
      <Button variant="contained" disabled={!item.can_apply_test || busy || !!job} onClick={() => selectJob(item)} sx={{ minHeight: 44 }}>{t('Ứng tuyển thử nghiệm')}</Button>
      {!item.can_apply_test && <Typography variant="caption" display="block" sx={{ mt: 1 }}>{t('Chưa mở nhận hồ sơ thử nghiệm hoặc rubric chưa duyệt.')}</Typography>}
    </CardContent></Card>)}</Stack>
    {loading && <CircularProgress aria-label={t('Đang tải')} sx={{ mt: 2 }} />}
    {cursor && !loading && !error && <Button sx={{ mt: 2, minHeight: 44 }} variant="outlined" onClick={() => void load(cursor)}>{t('Xem thêm')}</Button>}
    {job && <Card variant="outlined" sx={{ mt: 4 }} data-testid="careers-apply-form"><CardContent>
      <Box component="form" onSubmit={apply} noValidate>
        <Stack spacing={2}>
          <Typography variant="h2" sx={{ fontSize: { xs: 20, md: 23 }, lineHeight: 1.3 }}>{t('Ứng tuyển thử nghiệm: {0}', job.title)}</Typography>
          <TextField disabled={busy} name="name" label={t('Tên tổng hợp')} required fullWidth autoComplete="name" inputProps={{ maxLength: 200 }} />
          <TextField disabled={busy} name="email" type="email" label={t('Email tổng hợp @example.test')} required fullWidth autoComplete="email" inputProps={{ maxLength: 254 }} />
          <TextField disabled={busy} name="phone" type="tel" label={t('Điện thoại tổng hợp (tùy chọn)')} fullWidth autoComplete="tel" inputProps={{ maxLength: 50 }} />
          {/* Chọn tệp bằng nút lớn thay vì input mặc định của trình duyệt: trên điện
              thoại ô file gốc bé, khó bấm và không hiện tên tệp đã chọn. */}
          <Box>
            <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{t('CV tổng hợp PDF hoặc DOCX, tối đa 10 MB')}</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'stretch', sm: 'center' }}>
              <Button component="label" variant="outlined" disabled={busy} sx={{ minHeight: 44 }} data-testid="careers-cv-pick">
                {t('Chọn tệp CV')}
                <input
                  hidden
                  name="cv"
                  type="file"
                  accept=".pdf,.docx"
                  disabled={busy}
                  data-testid="careers-cv-input"
                  onChange={event => setCvName(event.target.files?.[0]?.name || '')}
                />
              </Button>
              <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: 'anywhere' }} data-testid="careers-cv-name">
                {cvName || t('Chưa chọn tệp nào.')}
              </Typography>
            </Stack>
          </Box>
          <FormControlLabel control={<Checkbox disabled={busy} checked={optedIn} onChange={e => setOptedIn(e.target.checked)} />} label={t('Tôi riêng biệt đồng ý tham gia Talent Pool thử nghiệm trong 7 ngày. Không bắt buộc để nộp.')} />
          {optedIn && <Alert severity="info" sx={{ overflowWrap: 'anywhere' }}>
            <Typography variant="body2">{t('Mã rút lựa chọn (sao chép trước khi gửi; nếu mất kết nối hãy giữ nguyên form để thử lại):')} <Box component="code" sx={{ overflowWrap: 'anywhere' }}>{poolToken}</Box></Typography>
            <Typography variant="body2">{t('Dùng tại /pool-withdraw; rút không tự xóa hồ sơ ứng tuyển.')}</Typography>
          </Alert>}
          <Typography variant="body2">{t('Nếu gặp lỗi sau khi gửi, giữ nguyên form và mã rút để thử lại. Một yêu cầu mới có thể tạo thêm hồ sơ; hệ thống chưa tự phát hiện mọi hồ sơ trùng.')}</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
            <Button type="submit" variant="contained" disabled={busy} sx={{ minHeight: 44 }}>{t('Gửi hồ sơ thử nghiệm')}</Button>
            <Button type="button" disabled={busy} onClick={() => { setJob(null); setCvName(''); }} sx={{ minHeight: 44 }}>{t('Hủy')}</Button>
          </Stack>
        </Stack>
      </Box>
    </CardContent></Card>}
  </Container>;
}
