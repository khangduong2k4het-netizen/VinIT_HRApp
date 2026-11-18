'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography,
} from '@mui/material';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { POOL_REASONS, type PoolState } from '@/lib/talentPool';

/** P3-1: HR marks an application into the Talent Pool so it can be reused for other positions. */
export default function TalentPoolPanel({ applicationId, versionKey }: { applicationId: string; versionKey?: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<PoolState | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('STRONG_FIT');
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [reference, setReference] = useState('');

  const load = useCallback(async () => {
    try { setState((await talentPoolApi.state(applicationId)).data); setError(''); }
    catch { setError(t('Không thể tải trạng thái Talent Pool')); }
  }, [applicationId, t]);
  useEffect(() => { load(); }, [load, versionKey]);

  const run = async (action: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try { await action(); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể cập nhật Talent Pool')); }
    finally { setBusy(false); }
  };

  return (
    <Card sx={{ mb: 3 }}><CardContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">{t('Talent Pool')}</Typography>
          {state?.marked && <Chip size="small" color="success" label={t('Đang trong Talent Pool')} />}
        </Box>
        {state?.expires_on && (
          <Typography variant="caption" color="text.secondary">{t('Được dùng lại đến hết ngày {0}', state.expires_on)}</Typography>
        )}
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {t('Hồ sơ trong Talent Pool được quét lại khi có vị trí mới phù hợp. Chỉ áp dụng cho hồ sơ ứng viên đã đồng ý cho dùng lại.')}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError('')}>{t(error)}</Alert>}
      {state && !state.marked && !state.can_mark && state.reason_text && (
        <Alert severity="info">{t(state.reason_text)}</Alert>
      )}
      {state && !state.marked && state.can_mark && (
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField select size="small" label={t('Lý do')} value={reason} onChange={e => setReason(e.target.value)} sx={{ minWidth: 240 }}>
            {Object.entries(POOL_REASONS).map(([code, label]) => <MenuItem key={code} value={code}>{t(label)}</MenuItem>)}
          </TextField>
          <Button variant="contained" color="secondary" disabled={busy}
            onClick={() => run(() => talentPoolApi.mark(applicationId, reason))}>{t('Đưa vào Talent Pool')}</Button>
        </Box>
      )}
      {state?.marked && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" disabled={busy} onClick={() => run(() => talentPoolApi.unmark(applicationId))}>
            {t('Bỏ khỏi Talent Pool')}
          </Button>
        </Box>
      )}
      {state && state.reason !== 'NO_CONSENT' && state.reason !== 'CONSENT_WITHDRAWN' && (
        <Button size="small" color="error" sx={{ mt: 1 }} disabled={busy} onClick={() => { setReference(''); setWithdrawOpen(true); }}>
          {t('Ghi nhận ứng viên rút đồng ý')}
        </Button>
      )}

      <Dialog open={withdrawOpen} onClose={() => !busy && setWithdrawOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('Ghi nhận ứng viên rút đồng ý')}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('Hồ sơ sẽ bị gỡ khỏi Talent Pool và không còn được quét cho vị trí khác. Việc xóa dữ liệu vẫn theo hàng đợi lưu trữ.')}
          </Alert>
          <TextField fullWidth size="small" label={t('Số tham chiếu yêu cầu (tùy chọn, không ghi thông tin cá nhân)')}
            value={reference} onChange={e => setReference(e.target.value)} inputProps={{ maxLength: 100 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWithdrawOpen(false)} disabled={busy}>{t('Hủy')}</Button>
          <Button color="error" variant="contained" disabled={busy}
            onClick={() => run(async () => { await talentPoolApi.withdrawConsent(applicationId, reference.trim() || undefined); setWithdrawOpen(false); })}>
            {t('Xác nhận rút đồng ý')}
          </Button>
        </DialogActions>
      </Dialog>
    </CardContent></Card>
  );
}
