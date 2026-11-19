'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControlLabel, Paper, Switch, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useI18n } from '@/i18n/I18nProvider';
import { departmentsApi } from '@/lib/api';
import type { Department } from '@/types';

const renderCode = (codeFormat: string, sequence: number) =>
  codeFormat.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) =>
    String(sequence).padStart((zeros || '').length || 1, '0'));

export default function AdminDepartmentsPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Department | null>(null);
  const [name, setName] = useState('');
  const [codeFormat, setCodeFormat] = useState('');
  const [isActive, setIsActive] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await departmentsApi.list(true);
      setItems(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải danh sách phòng ban."));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const resetForm = () => {
    setOpen(false);
    setEditing(null);
    setName('');
    setCodeFormat('');
    setIsActive(true);
    setDialogError(null);
  };
  const create = () => { resetForm(); setSuccess(null); setOpen(true); };
  const edit = (department: Department) => {
    setEditing(department);
    setName(department.name);
    setCodeFormat(department.code_format);
    setIsActive(department.is_active);
    setDialogError(null);
    setSuccess(null);
    setOpen(true);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setDialogError(null);
    const normalizedFormat = codeFormat.trim().toUpperCase();
    const placeholders = normalizedFormat.match(/\{SEQ(?::0+)?\}/g) || [];
    if (!name.trim()) { setDialogError(t("Vui lòng nhập tên phòng ban.")); return; }
    if (placeholders.length !== 1) {
      setDialogError(t("Mã định dạng phải chứa đúng một {SEQ} hoặc {SEQ:000}, ví dụ REQ-IT-{SEQ:000}"));
      return;
    }
    try {
      setSaving(true);
      const payload = { name: name.trim(), code_format: normalizedFormat, is_active: isActive };
      if (editing) {
        await departmentsApi.update(editing.department_id, payload);
        setSuccess(t("Đã cập nhật phòng ban."));
      } else {
        await departmentsApi.create(payload);
        setSuccess(t("Đã tạo phòng ban."));
      }
      resetForm();
      await load();
    } catch (err: any) {
      setDialogError(err.response?.data?.detail || t("Không thể lưu phòng ban."));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (department: Department) => {
    if (!window.confirm(t("Xóa phòng ban {0}?", department.name))) return;
    setError(null);
    setSuccess(null);
    try {
      await departmentsApi.delete(department.department_id);
      setSuccess(t("Đã xóa phòng ban."));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể xóa phòng ban."));
    }
  };

  return <Box>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
      <Box>
        <Typography variant="h1" sx={{ fontSize: 26, color: '#0A2B57' }}>{t("Quản lý phòng ban")}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {t("Quản lý đơn vị/phòng ban và mã định dạng dùng để tự sinh mã vị trí")}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>{t("Làm mới")}</Button>
        <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={create}>{t("Thêm phòng ban")}</Button>
      </Box>
    </Box>

    {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
    {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{t(success)}</Alert>}
    <Alert severity="info" sx={{ mb: 3 }}>
      {t("Mã định dạng là mẫu mã vị trí của phòng ban. Ví dụ REQ-IT-{SEQ:000} sẽ sinh REQ-IT-001, REQ-IT-002 khi tạo vị trí. Phòng ban đã có vị trí không thể xóa; hãy tắt trạng thái hoạt động nếu không còn dùng.")}
    </Alert>

    {loading ? <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" aria-label={t("Đang tải phòng ban")} /></Box>
      : !error && (items.length === 0 ? <Paper sx={{ p: 4, textAlign: 'center' }}>{t("Chưa có phòng ban nào.")}</Paper> : <>
        <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
          {items.map((department) => <Card key={department.department_id}><CardContent>
            <Typography fontWeight={700}>{department.name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{department.code_format}</Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>{t("Mã vị trí tiếp theo: {0}", renderCode(department.code_format, department.next_sequence))}</Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 1 }}>
              <Chip size="small" color={department.is_active ? 'success' : 'default'} label={department.is_active ? t("Đang hoạt động") : t("Ngừng hoạt động")} />
              <Typography variant="body2">{t("{0} vị trí", department.position_count || 0)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
              <Button onClick={() => edit(department)} aria-label={t("Chỉnh sửa phòng ban {0}", department.name)}>{t("Chỉnh sửa")}</Button>
              <Button color="error" onClick={() => remove(department)} aria-label={t("Xóa phòng ban {0}", department.name)}>{t("Xóa")}</Button>
            </Box>
          </CardContent></Card>)}
        </Box>
        <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' } }}>
          <Table aria-label={t("Danh sách phòng ban")}>
            <TableHead><TableRow>
              <TableCell>{t("Tên phòng ban")}</TableCell>
              <TableCell>{t("Mã định dạng")}</TableCell>
              <TableCell>{t("Mã vị trí tiếp theo")}</TableCell>
              <TableCell>{t("Số vị trí")}</TableCell>
              <TableCell>{t("Trạng thái")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow></TableHead>
            <TableBody>{items.map((department) => <TableRow key={department.department_id}>
              <TableCell>{department.name}</TableCell>
              <TableCell>{department.code_format}</TableCell>
              <TableCell>{renderCode(department.code_format, department.next_sequence)}</TableCell>
              <TableCell>{department.position_count || 0}</TableCell>
              <TableCell><Chip size="small" color={department.is_active ? 'success' : 'default'} label={department.is_active ? t("Đang hoạt động") : t("Ngừng hoạt động")} /></TableCell>
              <TableCell align="right">
                <Button onClick={() => edit(department)} aria-label={t("Chỉnh sửa phòng ban {0}", department.name)}>{t("Chỉnh sửa")}</Button>
                <Button color="error" onClick={() => remove(department)} aria-label={t("Xóa phòng ban {0}", department.name)}>{t("Xóa")}</Button>
              </TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </TableContainer>
      </>)}

    <Dialog open={open} onClose={() => { if (!saving) resetForm(); }} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={save}>
        <DialogTitle>{editing ? t("Chỉnh sửa phòng ban") : t("Thêm phòng ban")}</DialogTitle>
        <DialogContent dividers>
          {dialogError && <Alert severity="error" sx={{ mb: 2 }}>{t(dialogError)}</Alert>}
          <TextField label={t("Tên phòng ban")} value={name} onChange={(e) => setName(e.target.value)} fullWidth required margin="normal" inputProps={{ maxLength: 160 }} />
          <TextField
            label={t("Mã định dạng")}
            value={codeFormat}
            onChange={(e) => setCodeFormat(e.target.value.toUpperCase())}
            fullWidth required margin="normal"
            placeholder="REQ-IT-{SEQ:000}"
            helperText={t("Dùng {SEQ} hoặc {SEQ:000} cho số thứ tự. Ví dụ: REQ-IT-{SEQ:000} → REQ-IT-001.")}
            inputProps={{ maxLength: 80 }}
          />
          <Box sx={{ mt: 1, p: 1.5, backgroundColor: '#F8FAFC', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary">{t("Mã vị trí tiếp theo")}</Typography>
            <Typography fontWeight={700}>{codeFormat.trim() ? renderCode(codeFormat.trim().toUpperCase(), editing?.next_sequence || 1) : '—'}</Typography>
          </Box>
          <FormControlLabel
            control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />}
            label={t("Đang hoạt động")}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={resetForm} disabled={saving}>{t("Hủy")}</Button>
          <Button type="submit" variant="contained" color="secondary" disabled={saving}>
            {saving ? <CircularProgress size={20} color="inherit" /> : t("Lưu phòng ban")}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  </Box>;
}
