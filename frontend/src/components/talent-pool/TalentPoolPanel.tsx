'use client';

// P3-1: lets the HR of the source position put an application into the Talent Pool or take it out.
// The backend refuses when the candidate has not given (or has withdrawn) consent for reuse.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography } from '@mui/material';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { MARK_REASONS } from '@/lib/talentPool';

type PoolState = { marked: boolean; can_mark: boolean; can_withdraw_consent?: boolean; reason: string | null; reason_text: string | null; expires_on: string | null };

// refreshKey: any value that changes when the application changes (for example its status), so the
// panel reloads the pool state without a page refresh.
export default function TalentPoolPanel({ applicationId, refreshKey }: { applicationId: string; refreshKey?: string | null }) {
  const { t, locale } = useI18n();
  const [state, setState] = useState<PoolState | null>(null);
  const [reason, setReason] = useState('STRONG_FIT');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [reference, setReference] = useState('');
  const load = useCallback(() => {
    talentPoolApi.state(applicationId).then(r => setState(r.data)).catch(() => setState(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId, refreshKey]);
  useEffect(() => { load(); }, [load]);
  const act = async (mark: boolean) => {
    setBusy(true); setError('');
    try { if (mark) await talentPoolApi.mark(applicationId, reason); else await talentPoolApi.unmark(applicationId); load(); }
    catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? localizeServerMessage(detail, locale) : t('Không thể cập nhật Talent Pool'));
    } finally { setBusy(false); }
  };
  const withdraw = async () => {
    setBusy(true); setError('');
    try { await talentPoolApi.withdrawConsent(applicationId, reference.trim() || undefined); setWithdrawOpen(false); load(); }
    catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? localizeServerMessage(detail, locale) : t('Không thể cập nhật Talent Pool'));
    } finally { setBusy(false); }
  };
  if (!state) return null;
  return <Box sx={{ mb: 2, p: 1.5, border: '1px solid #E4E7EC', borderRadius: 1, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
    <Typography variant="body2"><strong>{t('Talent Pool')}</strong></Typography>
    {state.marked
      ? <>
        <Chip size="small" color="success" label={t('Đang trong pool')} />
        {state.expires_on && <Typography variant="caption" color="text.secondary">{t('Lưu đến {0}', state.expires_on)}</Typography>}
        <Button size="small" disabled={busy} onClick={() => act(false)}>{t('Bỏ khỏi Talent Pool')}</Button>
      </>
      : state.can_mark
        ? <>
          <TextField select size="small" label={t('Lý do')} value={reason} onChange={e => setReason(e.target.value)} sx={{ minWidth: 180 }}>
            {Object.entries(MARK_REASONS).map(([code, label]) => <MenuItem key={code} value={code}>{t(label)}</MenuItem>)}
          </TextField>
          <Button size="small" variant="outlined" disabled={busy} onClick={() => act(true)}>{t('Đưa vào Talent Pool')}</Button>
        </>
        : <Typography variant="caption" color="text.secondary">
          {state.reason_text ? localizeServerMessage(state.reason_text, locale) : t('Chưa đủ điều kiện vào Talent Pool')}
        </Typography>}
    {state.can_withdraw_consent && state.reason !== 'NO_CONSENT' && state.reason !== 'CONSENT_WITHDRAWN' && (
      <Button size="small" color="error" disabled={busy} onClick={() => { setReference(''); setWithdrawOpen(true); }}>
        {t('Ghi nhận ứng viên rút đồng ý')}
      </Button>
    )}
    {error && <Alert severity="error" sx={{ width: '100%' }}>{error}</Alert>}
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
        <Button color="error" variant="contained" disabled={busy} onClick={withdraw}>{t('Xác nhận rút đồng ý')}</Button>
      </DialogActions>
    </Dialog>
  </Box>;
}
