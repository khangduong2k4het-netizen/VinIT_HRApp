'use client';

// P3-1: lets the HR of the source position put an application into the Talent Pool or take it out.
// The backend refuses when the candidate has not given (or has withdrawn) consent for reuse.
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, MenuItem, TextField, Typography } from '@mui/material';
import { talentPoolApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';
import { MARK_REASONS } from '@/lib/talentPool';

type PoolState = { marked: boolean; can_mark: boolean; reason: string | null; reason_text: string | null; expires_on: string | null };

export default function TalentPoolPanel({ applicationId }: { applicationId: string }) {
  const { t, locale } = useI18n();
  const [state, setState] = useState<PoolState | null>(null);
  const [reason, setReason] = useState('STRONG_FIT');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    talentPoolApi.state(applicationId).then(r => setState(r.data)).catch(() => setState(null));
  }, [applicationId]);
  useEffect(() => { load(); }, [load]);
  const act = async (mark: boolean) => {
    setBusy(true); setError('');
    try { if (mark) await talentPoolApi.mark(applicationId, reason); else await talentPoolApi.unmark(applicationId); load(); }
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
    {error && <Alert severity="error" sx={{ width: '100%' }}>{error}</Alert>}
  </Box>;
}
