'use client';

import { useState } from 'react';
import {
  Alert, Box, Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControlLabel, FormGroup, FormLabel, Radio, RadioGroup, Typography,
} from '@mui/material';
import { candidateReportsApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import { localizeServerMessage } from '@/i18n/serverMessages';

/** F2.09 export columns. Contact details (email/phone) are deliberately not offered. */
const COLUMN_OPTIONS: { key: string; label: string }[] = [
  { key: 'candidate', label: 'Tên ứng viên' },
  { key: 'rank', label: 'Thứ hạng' },
  { key: 'application_status', label: 'Trạng thái hồ sơ' },
  { key: 'matching_status', label: 'Kết luận AI' },
  { key: 'score', label: 'Điểm' },
  { key: 'coverage', label: 'Độ phủ bằng chứng' },
  { key: 'criteria', label: 'Kết quả từng tiêu chí' },
  { key: 'evidence', label: 'Trích dẫn bằng chứng' },
  { key: 'profile', label: 'Học vấn, kinh nghiệm, chứng chỉ' },
];
const DEFAULT_COLUMNS = ['candidate', 'rank', 'application_status', 'matching_status', 'score', 'coverage', 'criteria'];

async function errorMessage(error: unknown): Promise<string> {
  // Blob responses carry the API error as a JSON blob.
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  if (data instanceof Blob) {
    try { return localizeServerMessage(JSON.parse(await data.text())?.detail); } catch { /* fall through */ }
  }
  return localizeServerMessage((data as { detail?: unknown })?.detail);
}

export default function ExportReportDialog({ open, onClose, positionId, positionCode, selectedIds }: {
  open: boolean; onClose: () => void; positionId: string; positionCode?: string | null; selectedIds: string[];
}) {
  const { t, locale } = useI18n();
  const [format, setFormat] = useState<'xlsx' | 'pdf'>('xlsx');
  const [columns, setColumns] = useState<string[]>(DEFAULT_COLUMNS);
  const [scope, setScope] = useState<'all' | 'selected'>('all');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const toggle = (key: string) =>
    setColumns(old => old.includes(key) ? old.filter(k => k !== key) : [...old, key]);

  const submit = async () => {
    setBusy(true); setError('');
    try {
      const response = await candidateReportsApi.export(positionId, {
        format, columns, language: locale,
        ...(scope === 'selected' && selectedIds.length ? { application_ids: selectedIds } : {}),
      });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
      link.href = url;
      link.download = `HRA_${(positionCode || 'position').replace(/[^A-Za-z0-9_-]+/g, '-')}_${stamp}.${format}`;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      onClose();
    } catch (e) {
      setError(await errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("Xuất báo cáo ứng viên")}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <FormLabel>{t("Định dạng")}</FormLabel>
        <RadioGroup row value={format} onChange={e => setFormat(e.target.value as 'xlsx' | 'pdf')} sx={{ mb: 2 }}>
          <FormControlLabel value="xlsx" control={<Radio />} label="Excel (.xlsx)" />
          <FormControlLabel value="pdf" control={<Radio />} label="PDF" />
        </RadioGroup>
        <FormLabel>{t("Phạm vi")}</FormLabel>
        <RadioGroup value={scope} onChange={e => setScope(e.target.value as 'all' | 'selected')} sx={{ mb: 2 }}>
          <FormControlLabel value="all" control={<Radio />} label={t("Tất cả hồ sơ đã đánh giá theo bộ tiêu chí hiện tại")} />
          <FormControlLabel value="selected" disabled={!selectedIds.length} control={<Radio />}
            label={t("Chỉ {0} hồ sơ đang chọn để so sánh", selectedIds.length)} />
        </RadioGroup>
        <FormLabel>{t("Cột thông tin")}</FormLabel>
        <FormGroup sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          {COLUMN_OPTIONS.map(option => (
            <FormControlLabel key={option.key} label={t(option.label)}
              control={<Checkbox checked={columns.includes(option.key)} onChange={() => toggle(option.key)} />} />
          ))}
        </FormGroup>
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            {t("File không bao giờ chứa email hay số điện thoại của ứng viên. Mỗi lần xuất được ghi vào nhật ký audit.")}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>{t("Hủy")}</Button>
        <Button variant="contained" color="secondary" onClick={submit} disabled={busy || !columns.length}
          startIcon={busy ? <CircularProgress size={16} color="inherit" /> : undefined}>{t("Xuất file")}</Button>
      </DialogActions>
    </Dialog>
  );
}
