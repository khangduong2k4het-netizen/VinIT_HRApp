'use client';

import { useCallback, useEffect, useState } from 'react';
import { careersFailure } from '@/lib/syntheticIntake';
import { Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container, FormControlLabel, Stack, TextField, Typography } from '@mui/material';

type Job = { position_id: string; position_code: string; title: string; org_unit: string | null; work_location: string | null; work_mode: string | null; employment_type: string | null; application_deadline_at: string; description: string | null; can_apply_test: boolean };
type JobPage = { items: Job[]; next_cursor: string | null };

export default function CareersPage() {
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
    setJob(selected); setOptedIn(false); setSavedToken(''); setError(''); setSuccess('');
  };
  const apply = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!job || busy) return;
    setBusy(true); setError(''); setSuccess('');
    try {
      const data = new FormData(event.currentTarget);
      data.set('request_id', requestId);
      data.set('pool_opt_in', optedIn ? 'true' : 'false');
      data.set('pool_token', optedIn ? poolToken : '');
      const res = await fetch(`/v1/careers/jobs/${job.position_id}/apply`, { method: 'POST', body: data, cache: 'no-store' });
      if (!res.ok) {
        const result = await res.json().catch(() => ({}));
        setError(careersFailure(res.status, result.detail));
        return;
      }
      setSuccess('Đã tiếp nhận yêu cầu thử nghiệm; CV vẫn cần được xử lý. Gửi lại cùng yêu cầu không tạo thêm hồ sơ.'); setSavedToken(optedIn ? poolToken : ''); setJob(null);
    } catch { setError(careersFailure(null, null)); }
    finally { setBusy(false); }
  };
  return <Container maxWidth="md" sx={{ py: 5 }}>
    <Typography variant="h1" sx={{ fontSize: 30, mb: 2 }}>Vị trí đang tuyển dụng</Typography>
    <Alert severity="warning" sx={{ mb: 3 }}>Chỉ kiểm thử với CV và thông tin tổng hợp, email dạng @example.test. Không gửi thông tin cá nhân hoặc CV thật.</Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={!job ? <Button color="inherit" onClick={() => void load(cursor)}>Thử lại</Button> : undefined}>{error}</Alert>}
    {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
    {savedToken && <Alert severity="info" sx={{ mb: 2 }}>Mã rút lựa chọn thử nghiệm: <Box component="code" sx={{ overflowWrap: 'anywhere' }}>{savedToken}</Box>. Lưu mã và dùng tại /pool-withdraw.</Alert>}
    {!loading && !error && !jobs.length && <Typography>Hiện chưa có vị trí còn hạn.</Typography>}
    <Stack spacing={2}>{jobs.map(item => <Card variant="outlined" key={item.position_id}><CardContent>
      <Typography variant="h2" sx={{ fontSize: 21 }}>{item.title}</Typography>
      <Typography>{[item.position_code, item.org_unit, item.work_location, item.work_mode, item.employment_type].filter(Boolean).join(' · ')}</Typography>
      <Typography>Hạn: {new Date(item.application_deadline_at).toLocaleString('vi-VN')}</Typography>
      {item.description ? <Typography component="p" sx={{ whiteSpace: 'pre-wrap', my: 2 }}>{item.description}</Typography> : <Typography sx={{ my: 2 }}>Chưa có mô tả công việc.</Typography>}
      <Button variant="contained" disabled={!item.can_apply_test || busy || !!job} onClick={() => selectJob(item)}>Ứng tuyển thử nghiệm</Button>
      {!item.can_apply_test && <Typography variant="caption" display="block">Chưa mở nhận hồ sơ thử nghiệm hoặc rubric chưa duyệt.</Typography>}
    </CardContent></Card>)}</Stack>
    {loading && <CircularProgress aria-label="Đang tải" sx={{ mt: 2 }} />}
    {cursor && !loading && !error && <Button sx={{ mt: 2 }} variant="outlined" onClick={() => void load(cursor)}>Xem thêm</Button>}
    {job && <Box component="form" onSubmit={apply} sx={{ mt: 4 }}><Stack spacing={2}>
      <Typography variant="h2" sx={{ fontSize: 23 }}>Ứng tuyển thử nghiệm: {job.title}</Typography>
      <TextField disabled={busy} name="name" label="Tên tổng hợp" required inputProps={{ maxLength: 200 }} />
      <TextField disabled={busy} name="email" type="email" label="Email tổng hợp @example.test" required inputProps={{ maxLength: 254 }} />
      <TextField disabled={busy} name="phone" label="Điện thoại tổng hợp (tùy chọn)" inputProps={{ maxLength: 50 }} />
      <label>CV tổng hợp PDF hoặc DOCX, tối đa 10 MB <input disabled={busy} name="cv" type="file" accept=".pdf,.docx" required /></label>
      <FormControlLabel control={<Checkbox disabled={busy} checked={optedIn} onChange={e => setOptedIn(e.target.checked)} />} label="Tôi riêng biệt đồng ý tham gia Talent Pool thử nghiệm trong 7 ngày. Không bắt buộc để nộp." />
      {optedIn && <Alert severity="info">Mã rút lựa chọn (sao chép trước khi gửi; nếu mất kết nối hãy giữ nguyên form để thử lại): <Box component="code" sx={{ overflowWrap: 'anywhere' }}>{poolToken}</Box>. Dùng tại /pool-withdraw; rút không tự xóa hồ sơ ứng tuyển.</Alert>}
      <Typography variant="body2">Nếu gặp lỗi sau khi gửi, giữ nguyên form và mã rút để thử lại. Một yêu cầu mới có thể tạo thêm hồ sơ; hệ thống chưa tự phát hiện mọi hồ sơ trùng.</Typography>
      <Stack direction="row" spacing={1}><Button type="submit" variant="contained" disabled={busy}>Gửi hồ sơ thử nghiệm</Button><Button type="button" disabled={busy} onClick={() => setJob(null)}>Hủy</Button></Stack>
    </Stack></Box>}
  </Container>;
}
