'use client';

import { useEffect, useState } from 'react';
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material';
import apiClient, { positionsApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type Position = { position_id: string; title: string; position_code: string };
type Result = { application_id: string; display_name: string; consent_expires_at: string; retention_expires_at: string };

export default function TalentPool() {
  const { dateLocale } = useI18n();
  const [positions, setPositions] = useState<Position[]>([]);
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [items, setItems] = useState<Result[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { positionsApi.listAll().then(setPositions).catch(() => setError('Không thể tải vị trí.')); }, []);
  const reset = () => { setItems(null); setCursor(null); setError(''); };
  const scan = async (next: string | null = null) => {
    if (busy) return;
    setBusy(true); setError('');
    if (!next) { setItems(null); setCursor(null); }
    try {
      const result = await apiClient.get('/talent-pool/scan', { params: { source_position_id: source, target_position_id: target, ...(next ? { cursor: next } : {}) } });
      setItems(previous => next ? [...(previous || []), ...result.data.items] : result.data.items);
      setCursor(result.data.next_cursor);
    } catch (err: any) { setError(err.response?.data?.detail || 'Không thể tìm hồ sơ.'); }
    finally { setBusy(false); }
  };
  return <Box><Typography variant="h1" sx={{ fontSize: 28, mb: 2 }}>Talent Pool</Typography>
    <Alert severity="info" sx={{ mb: 2 }}>Chỉ hồ sơ đồng ý riêng, còn hạn và được phép truy cập mới xuất hiện. Danh sách chỉ phản ánh điều kiện tại thời điểm tìm, không phải đánh giá hay xếp hạng. Hãy tìm lại trước khi sử dụng: consent có thể đã rút hoặc hết hạn sau lần tìm trước.</Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
    <Stack spacing={2} sx={{ maxWidth: 640 }}>
      <TextField select label="Vị trí nguồn" value={source} disabled={busy} onChange={e => { setSource(e.target.value); reset(); }}>{positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}</TextField>
      <TextField select label="Vị trí đích có rubric duyệt" value={target} disabled={busy} onChange={e => { setTarget(e.target.value); reset(); }}>{positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}</TextField>
      <Button variant="contained" disabled={busy || !source || !target || source === target} onClick={() => void scan()}>Tìm hồ sơ đủ điều kiện</Button>
      {items && <><Typography>{items.length} hồ sơ trong các trang đã tải {items.length === 0 && '— không có kết quả đủ điều kiện tại thời điểm tìm.'}</Typography>{items.map(i => <Typography key={i.application_id}>{i.display_name} · consent hết hạn {new Date(i.consent_expires_at).toLocaleString(dateLocale)}</Typography>)}</>}
      {cursor && <Button disabled={busy} onClick={() => void scan(cursor)}>Xem thêm</Button>}
    </Stack>
  </Box>;
}
