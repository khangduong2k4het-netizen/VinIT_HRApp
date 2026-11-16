'use client';

import { useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { rubricApi } from '@/lib/api';

type Rubric = { template_version_id: string; title: string; family_name: string; level_band: string | null; version_number: number; status: string };
export default function ApplyRubric({ positionId, disabled, onApplied }: { positionId: string; disabled: boolean; onApplied: () => Promise<void> }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<Rubric[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const show = async () => {
    setOpen(true); setSelected(''); setError(''); setBusy(true);
    try { const res = await rubricApi.templates(); setVersions(res.data.filter((v: Rubric) => v.status === 'PUBLISHED')); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải thư viện rubric.')); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    try { setBusy(true); setError(''); await rubricApi.apply(positionId, selected); setOpen(false); await onApplied(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể áp dụng rubric.')); }
    finally { setBusy(false); }
  };
  return <><Button variant="outlined" disabled={disabled} onClick={show}>{t('Dùng rubric đã xuất bản')}</Button>
    <Dialog open={open} onClose={() => !busy && setOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>{t('Áp dụng rubric vào vị trí')}</DialogTitle>
      <DialogContent>
        <Typography sx={{ mb: 2 }}>{t('Rubric tạo bộ tiêu chí nháp, không tự phê duyệt. HR cần rà soát và chọn luồng duyệt.')}</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
        {!busy && !versions.length && <Alert severity="info">{t('Chưa có rubric được xuất bản.')}</Alert>}
        <TextField select fullWidth label={t('Chọn rubric')} value={selected} disabled={busy || !versions.length} onChange={e => setSelected(e.target.value)}>
          {versions.map(v => <MenuItem key={v.template_version_id} value={v.template_version_id}>{v.title} · {v.family_name === 'Vận hành & Hành chính' ? t('Vận hành & Hành chính') : v.family_name} · v{v.version_number}{v.level_band ? ` · ${v.level_band}` : ''}</MenuItem>)}
        </TextField>
      </DialogContent><DialogActions><Button onClick={() => setOpen(false)} disabled={busy}>{t('Hủy')}</Button><Button variant="contained" disabled={busy || !selected} onClick={apply}>{t('Tạo bộ tiêu chí nháp')}</Button></DialogActions>
    </Dialog></>;
}
