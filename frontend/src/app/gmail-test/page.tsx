'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Checkbox, FormControlLabel, Stack, TextField, Typography } from '@mui/material';
import apiClient from '@/lib/api';

type Item = { receipt_id: string; message_id: string; status: string; reason: string | null; application_id: string | null; updated_at: string };
type Identity = { receipt_id: string; application_id: string; position_id: string; display_name: string; email: string; updated_at: string };
const statuses: Record<string, string> = { PENDING: 'Đang chờ', REVIEW: 'Cần HR kiểm tra', SPAM: 'Bị đánh dấu spam', MALWARE: 'Phát hiện mã độc', ACCEPTED: 'Đã tiếp nhận hồ sơ' };
const reasons: Record<string, string> = {
  MESSAGE_TOO_LARGE: 'Email quá lớn; dùng email giả nhỏ hơn.', SYNTHETIC_MARKER_REQUIRED: 'Thiếu tiêu đề bắt đầu [HRA-TEST].',
  POSITION_AMBIGUOUS: 'Không xác định được duy nhất mã vị trí.', ATTACHMENT_COUNT: 'Cần đúng một tệp CV giả.',
  ATTACHMENT_INVALID: 'Tệp CV không hợp lệ.', POSITION_NOT_READY: 'Vị trí chưa sẵn sàng; kiểm tra hạn và rubric.',
  POSITION_UNAVAILABLE: 'Không tìm thấy vị trí.', ANTIVIRUS_UNAVAILABLE: 'Máy quét mã độc không sẵn sàng; liên hệ quản trị viên.',
  SPAM_FILTER_UNAVAILABLE: 'Bộ lọc spam không sẵn sàng; liên hệ quản trị viên.', INTAKE_UNAVAILABLE: 'Nhận hồ sơ chưa sẵn sàng.',
  PROCESSING_UNAVAILABLE: 'Không thể xử lý; kiểm tra dịch vụ và thử lại.', MESSAGE_INVALID: 'Email không hợp lệ.',
  GMAIL_SPAM_OR_TRASH: 'Gmail phân loại spam/thùng rác.', SPAM_FILTER: 'Bộ lọc đánh dấu spam.', MALWARE: 'Phát hiện mã độc; không mở hoặc xử lý tệp.',
};
const displayError = (err: any, fallback: string) => typeof err.response?.data?.detail === 'string' ? err.response.data.detail : fallback;

export default function GmailTestPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [page, setPage] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [spamMode, setSpamMode] = useState<string | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const load = useCallback(async () => {
    try { const result = await apiClient.get('/gmail-test/review'); setItems(result.data.items); setSpamMode(result.data.spam_mode); }
    catch (err: any) { setError(displayError(err, 'Không thể tải hàng đợi Gmail thử nghiệm.')); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const sync = async (next: string | null) => {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await apiClient.post('/gmail-test/sync', null, { params: next ? { page_token: next } : {} });
      setPage(result.data.next_page_token); setMessage(`Đã kiểm tra ${result.data.processed} email thử nghiệm trong trang này.`);
      await load();
    } catch (err: any) { setError(displayError(err, 'Không thể đồng bộ Gmail thử nghiệm.')); }
    finally { setBusy(false); }
  };
  const retry = async (item: Item) => {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await apiClient.post(`/gmail-test/review/${item.receipt_id}/retry`);
      setMessage(`Kết quả thử lại: ${statuses[result.data.status] || 'Cần kiểm tra'}.`);
      await load();
    } catch (err: any) { setError(displayError(err, 'Không thể thử lại email.')); }
    finally { setBusy(false); }
  };
  const edit = async (item: Item) => {
    if (busy) return;
    setBusy(true); setError(''); setMessage(''); setIdentity(null); setConfirmed(false);
    try {
      const result = await apiClient.get(`/gmail-test/review/${item.receipt_id}/identity`);
      setIdentity(result.data); setName(result.data.display_name); setEmail(result.data.email);
    } catch (err: any) { setError(displayError(err, 'Không thể tải hồ sơ thử nghiệm.')); }
    finally { setBusy(false); }
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!identity || busy || !confirmed) return;
    setBusy(true); setError(''); setMessage('');
    try {
      await apiClient.put(`/gmail-test/review/${identity.receipt_id}/identity`, { display_name: name, email, expected_updated_at: identity.updated_at, confirm_synthetic: true });
      setMessage('Đã lưu thông tin giả do HR xác nhận. Đây không phải xác minh danh tính thật.'); setIdentity(null); setConfirmed(false);
    } catch (err: any) { setError(displayError(err, 'Không thể lưu; tải lại thông tin trước khi thử lại.')); }
    finally { setBusy(false); }
  };
  return <Box><Typography variant="h1" sx={{ fontSize: 28, mb: 2 }}>Gmail thử nghiệm</Typography>
    <Alert severity="warning" sx={{ mb: 2 }}>Chỉ HR Lead/quản trị viên. Chỉ dùng hộp Gmail thử nghiệm riêng, nhãn HRA_TEST, tiêu đề bắt đầu [HRA-TEST] và email/CV giả; không dùng dữ liệu thật. Đồng bộ thủ công, không sửa hoặc xóa email.</Alert>
    {spamMode === 'GMAIL_LABELS_ONLY_TEST' && <Alert severity="warning" sx={{ mb: 2 }}>Chỉ dùng phân loại spam/thùng rác của Gmail; không có SpamAssassin. Chỉ dành cho dữ liệu giả.</Alert>}
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <Stack direction="row" spacing={1}><Button variant="contained" disabled={busy} onClick={() => void sync(null)}>Kiểm tra Gmail</Button>
        {page && <Button variant="outlined" disabled={busy} onClick={() => void sync(page)}>Kiểm tra trang tiếp</Button>}</Stack>
      <Typography variant="body2">Với email cần kiểm tra, xử lý nguyên nhân rồi bấm Thử lại. Nếu nội dung thư đã gửi sai, gửi thư giả mới; nút Thử lại không sửa email. Spam và mã độc không được tự nhập lại. Chỉ hiển thị tối đa 100 kết quả gần nhất.</Typography>
      <Typography variant="h2" sx={{ fontSize: 20 }}>Kết quả gần đây</Typography>
      {!items.length && <Typography>Chưa có email đã kiểm tra.</Typography>}
      {items.map(item => <Card variant="outlined" key={item.receipt_id}><CardContent><Stack spacing={1}>
        <Typography>{new Date(item.updated_at).toLocaleString('vi-VN')} · {statuses[item.status] || 'Cần kiểm tra'}</Typography>
        {item.reason && <Typography>{reasons[item.reason] || 'Cần HR kiểm tra trong Gmail.'}</Typography>}
        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Button href={`https://mail.google.com/mail/u/0/#all/${encodeURIComponent(item.message_id)}`} target="_blank" rel="noopener noreferrer">Mở Gmail thử nghiệm</Button>
          {item.status === 'REVIEW' && <Button disabled={busy} onClick={() => void retry(item)}>Thử lại</Button>}
          {item.status === 'ACCEPTED' && item.application_id && <Button disabled={busy} onClick={() => void edit(item)}>Xác nhận thông tin giả</Button>}
        </Stack>
      </Stack></CardContent></Card>)}
      {identity && <Box component="form" onSubmit={save}><Stack spacing={2}>
        <Typography variant="h2" sx={{ fontSize: 20 }}>HR xác nhận thông tin giả</Typography>
        <Alert severity="warning">Không tự lấy danh tính từ người gửi. Chỉ nhập thông tin giả; không xác minh danh tính thật và không tạo consent Talent Pool. Nếu tác vụ đang chạy, chờ hoàn tất trước khi lưu.</Alert>
        <TextField required disabled={busy} label="Tên giả" value={name} onChange={e => setName(e.target.value)} inputProps={{ maxLength: 200 }} />
        <TextField required disabled={busy} type="email" label="Email giả @example.test" value={email} onChange={e => setEmail(e.target.value)} inputProps={{ maxLength: 254 }} />
        <FormControlLabel control={<Checkbox disabled={busy} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />} label="Tôi xác nhận đây chỉ là thông tin giả." />
        <Stack direction="row" spacing={1}><Button type="submit" variant="contained" disabled={busy || !confirmed}>Lưu thông tin giả</Button><Button type="button" disabled={busy} onClick={() => setIdentity(null)}>Hủy</Button></Stack>
      </Stack></Box>}
    </Stack>
  </Box>;
}
