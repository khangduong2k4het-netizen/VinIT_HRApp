'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, CardContent, CircularProgress, Container, Stack, Typography } from '@mui/material';

type Job = { position_id: string; position_code: string; title: string; org_unit: string | null; work_location: string | null; work_mode: string | null; employment_type: string | null; application_deadline_at: string; description: string | null };
type JobPage = { items: Job[]; next_cursor: string | null };

export default function CareersPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
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
  return <Container maxWidth="md" sx={{ py: 5 }}>
    <Typography variant="h1" sx={{ fontSize: 30, mb: 2 }}>Vị trí đang tuyển dụng</Typography>
    <Alert severity="info" sx={{ mb: 3 }}>Danh sách đang trong giai đoạn kiểm thử. Chức năng nộp hồ sơ chưa mở; vui lòng không gửi thông tin cá nhân hay CV.</Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => void load(cursor)}>Thử lại</Button>}>{error}</Alert>}
    {!loading && !error && !jobs.length && <Typography>Hiện chưa có vị trí còn hạn.</Typography>}
    <Stack spacing={2}>{jobs.map(job => <Card variant="outlined" key={job.position_id}><CardContent>
      <Typography variant="h2" sx={{ fontSize: 21 }}>{job.title}</Typography>
      <Typography>{[job.position_code, job.org_unit, job.work_location, job.work_mode, job.employment_type].filter(Boolean).join(' · ')}</Typography>
      <Typography>Hạn: {new Date(job.application_deadline_at).toLocaleString('vi-VN')}</Typography>
      {job.description ? <Typography component="p" sx={{ whiteSpace: 'pre-wrap', my: 2 }}>{job.description}</Typography> : <Typography sx={{ my: 2 }}>Chưa có mô tả công việc.</Typography>}
    </CardContent></Card>)}</Stack>
    {loading && <CircularProgress aria-label="Đang tải" sx={{ mt: 2 }} />}
    {cursor && !loading && !error && <Button sx={{ mt: 2 }} variant="outlined" onClick={() => void load(cursor)}>Xem thêm</Button>}
  </Container>;
}
