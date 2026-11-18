'use client';

import { useEffect, useState } from 'react';
import { Alert, Box, Button, Container, Stack, TextField, Typography } from '@mui/material';

export default function PoolWithdraw() {
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // A static form must not accept input before React installs its submit
  // handler: otherwise the browser can navigate without sending withdrawal.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true); setMessage(''); setError('');
    try {
      const response = await fetch('/v1/talent-pool/withdraw', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: token.trim() }) });
      if (!response.ok) throw new Error('Không thể thực hiện yêu cầu. Vui lòng kiểm tra mã và thử lại.');
      setMessage('Đã nhận yêu cầu. Nếu mã hợp lệ, lựa chọn Talent Pool đã được rút; phản hồi không xác nhận mã có tồn tại.'); setToken('');
    } catch (err) { setError(err instanceof Error ? err.message : 'Không thể thực hiện yêu cầu.'); }
    finally { setBusy(false); }
  };
  return <Container maxWidth="sm" sx={{ py: 5 }}><Typography variant="h1" sx={{ fontSize: 28, mb: 2 }}>Rút lựa chọn Talent Pool</Typography>
    <Alert severity="info" sx={{ mb: 2 }}>Rút lựa chọn ngừng sử dụng hồ sơ cho Talent Pool; không tự động xóa hồ sơ ứng tuyển. Phản hồi giống nhau cho mọi mã để bảo vệ thông tin; không xác nhận mã có tồn tại. Chưa có chức năng khôi phục mã tự động; nếu mất mã, liên hệ HR để xử lý thủ công.</Alert>
    {!ready && <Alert severity="info" sx={{ mb: 2 }}>Đang tải biểu mẫu; cần bật JavaScript để gửi yêu cầu.</Alert>}
    {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Box component="form" onSubmit={submit}><Stack spacing={2}>
      <TextField disabled={!ready || busy} label="Mã rút lựa chọn" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} required inputProps={{ maxLength: 64, pattern: '[0-9a-f]{64}' }} />
      <Button type="submit" variant="contained" disabled={!ready || busy}>Gửi yêu cầu rút</Button>
    </Stack></Box>
  </Container>;
}
