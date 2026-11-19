'use client';

import { useEffect, useState } from 'react';
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import apiClient, { positionsApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type Position = { position_id: string; title: string; position_code: string };
type Result = { application_id: string; position_id: string; display_name: string; expires_at: string };

export default function TalentPoolDemo() {
  const { dateLocale } = useI18n();
  const [positions, setPositions] = useState<Position[]>([]);
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [items, setItems] = useState<Result[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { positionsApi.listAll().then(setPositions).catch(() => setError('Không thể tải vị trí.')); }, []);
  const scan = async () => {
    setBusy(true); setError(''); setItems(null);
    try { const result = await apiClient.get('/careers-demo/pool/scan', { params: { source_position_id: source, target_position_id: target } }); setItems(result.data.items); }
    catch (err: any) { setError(err.response?.data?.detail || 'Không thể quét pool demo.'); }
    finally { setBusy(false); }
  };
  return <Box><Typography variant="h1" sx={{ fontSize: 28, mb: 2 }}>Talent Pool — DEMO</Typography>
    <Alert severity="warning" sx={{ mb: 2 }}>Chỉ dữ liệu tổng hợp, không dùng hồ sơ thật. Danh sách không phải kết quả đánh giá hay xếp hạng.</Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <TextField select label="Vị trí nguồn" value={source} onChange={e => { setSource(e.target.value); setItems(null); }}>{positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}</TextField>
      <TextField select label="Vị trí đích có rubric duyệt" value={target} onChange={e => { setTarget(e.target.value); setItems(null); }}>{positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}</TextField>
      <Button variant="contained" disabled={busy || !source || !target || source === target} onClick={scan}>Kiểm tra pool demo</Button>
      {items && <><Typography>{items.length} hồ sơ đủ điều kiện demo (tối đa 100)</Typography>{items.map(i => <Typography key={i.application_id}>{i.display_name} · hết hạn lựa chọn {new Date(i.expires_at).toLocaleString(dateLocale)}</Typography>)}</>}
    </Stack>
  </Box>;
}
