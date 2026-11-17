'use client';

import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import apiClient from '@/lib/api';

type Item = { receipt_id: string; message_id: string; status: string; reason: string | null; updated_at: string };
const reasons: Record<string, string> = {
  MESSAGE_TOO_LARGE: 'Email quá lớn', SYNTHETIC_MARKER_REQUIRED: 'Thiếu đánh dấu email giả',
  POSITION_AMBIGUOUS: 'Không xác định được duy nhất mã vị trí', ATTACHMENT_COUNT: 'Số tệp đính kèm không hợp lệ',
  ATTACHMENT_INVALID: 'Tệp CV không hợp lệ', POSITION_NOT_READY: 'Vị trí chưa sẵn sàng',
  POSITION_UNAVAILABLE: 'Không tìm thấy vị trí', ANTIVIRUS_UNAVAILABLE: 'Máy quét mã độc không sẵn sàng',
  SPAM_FILTER_UNAVAILABLE: 'Bộ lọc spam không sẵn sàng', INTAKE_UNAVAILABLE: 'Nhận hồ sơ chưa sẵn sàng',
  PROCESSING_UNAVAILABLE: 'Không thể xử lý; hãy kiểm tra dịch vụ', MESSAGE_INVALID: 'Email không hợp lệ',
  GMAIL_SPAM_OR_TRASH: 'Gmail phân loại spam/thùng rác', SPAM_FILTER: 'Bộ lọc đánh dấu spam', MALWARE: 'Phát hiện mã độc',
};

export default function GmailTestPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [page, setPage] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [spamMode, setSpamMode] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { const result = await apiClient.get('/gmail-test/review'); setItems(result.data.items); setSpamMode(result.data.spam_mode); }
    catch (err: any) { setError(err.response?.data?.detail || 'Không thể tải hàng đợi Gmail thử nghiệm.'); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const sync = async (next: string | null) => {
    if (busy) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await apiClient.post('/gmail-test/sync', null, { params: next ? { page_token: next } : {} });
      setPage(result.data.next_page_token); setMessage(`Đã kiểm tra ${result.data.processed} email thử nghiệm trong trang này.`);
      await load();
    } catch (err: any) { setError(err.response?.data?.detail || 'Không thể đồng bộ Gmail thử nghiệm.'); }
    finally { setBusy(false); }
  };
  return <Box><Typography variant="h1" sx={{ fontSize: 28, mb: 2 }}>Gmail thử nghiệm</Typography>
    <Alert severity="warning" sx={{ mb: 2 }}>Chỉ HR Lead/quản trị viên. Chỉ dùng hộp Gmail thử nghiệm riêng, nhãn HRA_TEST, tiêu đề bắt đầu [HRA-TEST] và email/CV giả; không dùng dữ liệu thật. Đây là đồng bộ thủ công, không sửa hoặc xóa email.</Alert>
    {spamMode === 'GMAIL_LABELS_ONLY_TEST' && <Alert severity="warning" sx={{ mb: 2 }}>Chỉ dùng phân loại spam/thùng rác của Gmail; không có SpamAssassin. Chỉ dành cho dữ liệu giả.</Alert>}
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
    <Stack spacing={2} sx={{ maxWidth: 760 }}>
      <Stack direction="row" spacing={1}><Button variant="contained" disabled={busy} onClick={() => void sync(null)}>Kiểm tra Gmail</Button>
        {page && <Button variant="outlined" disabled={busy} onClick={() => void sync(page)}>Kiểm tra trang tiếp</Button>}</Stack>
      <Typography variant="h2" sx={{ fontSize: 20 }}>Kết quả gần đây</Typography>
      {!items.length && <Typography>Chưa có email đã kiểm tra.</Typography>}
      {items.map(item => <Typography key={item.receipt_id}>{new Date(item.updated_at).toLocaleString('vi-VN')} · {item.status} {item.reason ? `· ${reasons[item.reason] || 'Cần HR kiểm tra trong Gmail'}` : ''} · <a href={`https://mail.google.com/mail/u/0/#all/${encodeURIComponent(item.message_id)}`} target="_blank" rel="noopener noreferrer">Mở trong Gmail thử nghiệm</a></Typography>)}
    </Stack>
  </Box>;
}
