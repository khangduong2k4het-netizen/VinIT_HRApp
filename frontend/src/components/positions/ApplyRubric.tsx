'use client';

import { useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { rubricApi } from '@/lib/api';

type Rubric = { template_version_id: string; title: string; family_name: string; job_family_id: string; level_band: string | null; version_number: number; status: string };
/**
 * @param jobFamilyId Nhóm vị trí của vị trí đang mở. Có nhóm thì thư viện rubric
 *   được lọc theo đúng nhóm đó, và rubric cùng nhóm được xếp lên đầu.
 *
 * Vì sao lọc: rubric được xây theo nhóm công việc ("IT & Digital" và "Vận hành &
 * Hành chính" có bộ tiêu chí khác hẳn nhau). Trước đây hộp chọn bày ra toàn bộ
 * rubric của mọi nhóm, nên HR rất dễ áp nhầm bộ tiêu chí vận hành cho một vị trí
 * kỹ thuật — sai ngay từ gốc và không ai phát hiện cho tới lúc chấm điểm.
 *
 * Không ẩn hẳn rubric khác nhóm: HR vẫn có thể cố ý dùng chéo, chỉ là không còn
 * là lựa chọn mặc định dễ bấm nhầm nữa.
 */
export default function ApplyRubric({ positionId, jobFamilyId, disabled, onApplied }: { positionId: string; jobFamilyId?: string | null; disabled: boolean; onApplied: () => Promise<void> }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<Rubric[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const show = async () => {
    setOpen(true); setSelected(''); setError(''); setBusy(true);
    try {
      const res = await rubricApi.templates();
      const published = res.data.filter((v: Rubric) => v.status === 'PUBLISHED');
      // Cùng nhóm lên trước; giữ nguyên thứ tự máy chủ trả về trong từng nhóm.
      setVersions(jobFamilyId
        ? [...published].sort((a: Rubric, b: Rubric) =>
            Number(b.job_family_id === jobFamilyId) - Number(a.job_family_id === jobFamilyId))
        : published);
    }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải thư viện rubric.')); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    const chosen = versions.find(v => v.template_version_id === selected);
    // Chỉ bật cờ khi rubric lệch nhóm — tức đúng trường hợp HR đã thấy nhãn đỏ.
    // Gửi cờ vô điều kiện thì chốt chặn ở máy chủ thành vô nghĩa.
    const crossFamily = !!jobFamilyId && !!chosen && chosen.job_family_id !== jobFamilyId;
    try { setBusy(true); setError(''); await rubricApi.apply(positionId, selected, crossFamily); setOpen(false); await onApplied(); }
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
          {versions.map(v => <MenuItem key={v.template_version_id} value={v.template_version_id}>
            {v.title} · {v.family_name === 'Vận hành & Hành chính' ? t('Vận hành & Hành chính') : v.family_name} · v{v.version_number}{v.level_band ? ` · ${v.level_band}` : ''}
            {/* Nói rõ khi lệch nhóm: đây là lựa chọn hợp lệ nhưng phải là lựa chọn có chủ ý. */}
            {jobFamilyId && v.job_family_id !== jobFamilyId && <Typography component="span" variant="caption" sx={{ ml: 1, color: '#B42318' }}>{t('(khác nhóm vị trí)')}</Typography>}
          </MenuItem>)}
        </TextField>
      </DialogContent><DialogActions><Button onClick={() => setOpen(false)} disabled={busy}>{t('Hủy')}</Button><Button variant="contained" disabled={busy || !selected} onClick={apply}>{t('Tạo bộ tiêu chí nháp')}</Button></DialogActions>
    </Dialog></>;
}
