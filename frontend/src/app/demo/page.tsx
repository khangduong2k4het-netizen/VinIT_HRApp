'use client';

import { useState } from 'react';
import { Alert, Box, Button, Container, Stack, Typography } from '@mui/material';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

export default function DemoHome() {
  const router = useRouter();
  const [error, setError] = useState('');
  const openHR = async () => {
    try {
      const response = await fetch('/v1/demo/session', { method: 'POST', cache: 'no-store' });
      if (!response.ok) throw new Error();
      const data = await response.json();
      localStorage.setItem('hra_access_token', data.access_token);
      router.push('/talent-pool-demo');
    } catch { setError('Demo HR không khả dụng. Hãy dùng backend demo cục bộ đã chuẩn bị.'); }
  };
  return <Container maxWidth="md" sx={{ py: 6 }}><Stack spacing={3}>
    <Typography variant="h1" sx={{ fontSize: 32 }}>Demo tuyển dụng — dữ liệu tổng hợp</Typography>
    <Alert severity="warning">Chỉ nhập dữ liệu giả và dùng file bên dưới. Không tải CV, email hoặc thông tin cá nhân thật lên bản demo này.</Alert>
    <Typography>Hai vị trí giả và một hồ sơ Talent Pool giả đã được chuẩn bị. Đăng nhập HR demo không cần mật khẩu và chỉ có tác dụng trên môi trường demo tách biệt.</Typography>
    {error && <Alert severity="error">{error}</Alert>}
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
      <Button component={Link} href="/careers-demo" variant="contained">1. Trang ứng tuyển giả</Button>
      <Button variant="outlined" onClick={openHR}>2–3. Mở workspace HR demo</Button>
    </Stack>
    <Box><Typography variant="h2" sx={{ fontSize: 20, mb: 1 }}>File mẫu để trình diễn</Typography>
      <Stack direction="row" spacing={2}><Button component="a" href="/v1/demo/fixture/cv">Tải CV giả (.docx)</Button><Button component="a" href="/v1/demo/fixture/email">Tải email giả (.eml)</Button></Stack>
    </Box>
    <Alert severity="info">Talent Pool chỉ liệt kê hồ sơ demo, không xếp hạng; email chỉ tải file offline, không kết nối Gmail. Trích xuất profile được giả lập; không chạy đánh giá hay xếp hạng AI.</Alert>
  </Stack></Container>;
}
