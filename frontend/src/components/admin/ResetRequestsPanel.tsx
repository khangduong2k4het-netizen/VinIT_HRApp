'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography,
} from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { adminApi } from '@/lib/api';

type ResetRequest = { request_id: string; email: string; display_name: string; reason: string; requested_at: string };

// Admin queue: people who forgot their password and wrote why. Approving emails them a one-time reset link.
export default function ResetRequestsPanel() {
  const { t } = useI18n();
  const [items, setItems] = useState<ResetRequest[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<ResetRequest | null>(null);
  const [note, setNote] = useState('');

  const load = useCallback(async () => {
    try {
      const response = await adminApi.listResetRequests('PENDING');
      setItems(response.data.items || []);
    } catch { setItems([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const fail = (err: any) => setError(typeof err?.response?.data?.detail === 'string' ? err.response.data.detail : t("Không thể xử lý yêu cầu."));

  const approve = async (item: ResetRequest) => {
    setBusy(item.request_id); setError(null); setNotice(null);
    try {
      await adminApi.approveResetRequest(item.request_id);
      setNotice("Đã duyệt: link đặt lại mật khẩu đã gửi tới email của tài khoản.");
      await load();
    } catch (err) { fail(err); } finally { setBusy(null); }
  };

  const reject = async () => {
    if (!rejecting) return;
    setBusy(rejecting.request_id); setError(null); setNotice(null);
    try {
      await adminApi.rejectResetRequest(rejecting.request_id, note.trim());
      setRejecting(null); setNote(''); setNotice("Đã từ chối yêu cầu.");
      await load();
    } catch (err) { fail(err); } finally { setBusy(null); }
  };

  if (items === null) return null;
  return <Card variant="outlined" sx={{ mb: 3 }}><CardContent>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
      <Typography variant="h6" sx={{ fontSize: 16 }}>{t("Yêu cầu đặt lại mật khẩu")}</Typography>
      {items.length > 0 && <Chip size="small" color="warning" label={items.length} />}
    </Box>
    {error && <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError(null)}>{t(error)}</Alert>}
    {notice && <Alert severity="success" sx={{ mb: 1.5 }} onClose={() => setNotice(null)}>{t(notice)}</Alert>}
    {items.length === 0
      ? <Typography variant="body2" color="text.secondary">{t("Không có yêu cầu nào đang chờ.")}</Typography>
      : items.map(item => <Box key={item.request_id} sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', py: 1.25, borderTop: '1px solid #E4E7EC' }}>
        <Box sx={{ minWidth: 0, flex: '1 1 320px' }}>
          <Typography variant="body2" fontWeight={600} sx={{ overflowWrap: 'anywhere' }}>{item.display_name} · {item.email}</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.reason}</Typography>
          <Typography variant="caption" color="text.secondary">{t("Gửi lúc")}: {new Date(item.requested_at).toLocaleString('vi-VN')}</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" variant="contained" disabled={busy !== null} onClick={() => approve(item)}>
            {busy === item.request_id ? <CircularProgress size={18} color="inherit" /> : t("Duyệt và gửi link")}
          </Button>
          <Button size="small" color="error" disabled={busy !== null} onClick={() => { setRejecting(item); setNote(''); }}>{t("Từ chối")}</Button>
        </Box>
      </Box>)}
    <Dialog open={rejecting !== null} onClose={() => busy === null && setRejecting(null)} maxWidth="sm" fullWidth>
      <DialogTitle>{t("Từ chối yêu cầu")}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 1 }}>{rejecting?.email}</Typography>
        <TextField fullWidth multiline minRows={2} label={t("Ghi chú (không bắt buộc)")} value={note} onChange={e => setNote(e.target.value)} inputProps={{ maxLength: 500 }} />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setRejecting(null)} disabled={busy !== null}>{t("Hủy")}</Button>
        <Button color="error" variant="contained" onClick={reject} disabled={busy !== null}>{t("Từ chối")}</Button>
      </DialogActions>
    </Dialog>
  </CardContent></Card>;
}
