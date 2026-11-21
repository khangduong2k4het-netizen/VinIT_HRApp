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
import { jobFamiliesApi } from '@/lib/api';

type JobFamily = {
  job_family_id: string;
  code: string;
  name: string;
  is_active: boolean;
  position_count: number;
  template_count: number;
};

export default function AdminJobFamiliesPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<JobFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<JobFamily | null>(null);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const response = await jobFamiliesApi.list(true);
      setItems(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể tải danh sách nhóm vị trí.'));
    } finally { setLoading(false); }
  }, [t]);

  useEffect(() => { void load(); }, [load]);

  const openCreate = () => {
    setEditing(null); setCode(''); setName(''); setDialogError(null); setOpen(true);
  };
  const openEdit = (item: JobFamily) => {
    setEditing(item); setCode(item.code); setName(item.name); setDialogError(null); setOpen(true);
  };

  const save = async () => {
    if (!name.trim() || (!editing && !code.trim())) return;
    setSaving(true); setDialogError(null); setSuccess(null);
    try {
      if (editing) {
        // Không gửi `code`: máy chủ không nhận đổi mã, và gửi lên chỉ gây hiểu
        // nhầm là đổi được.
        await jobFamiliesApi.update(editing.job_family_id, { name: name.trim() });
        setSuccess(t('Đã đổi tên nhóm vị trí.'));
      } else {
        await jobFamiliesApi.create({ code: code.trim(), name: name.trim() });
        setSuccess(t('Đã tạo nhóm vị trí. Giờ có thể tạo rubric mẫu cho nhóm này.'));
      }
      setOpen(false);
      await load();
    } catch (err: any) {
      setDialogError(err.response?.data?.detail || t('Không lưu được nhóm vị trí.'));
    } finally { setSaving(false); }
  };

  const toggleActive = async (item: JobFamily) => {
    setError(null); setSuccess(null);
    try {
      await jobFamiliesApi.update(item.job_family_id, { is_active: !item.is_active });
      setSuccess(item.is_active
        ? t('Đã tắt nhóm vị trí. Nhóm bị tắt không chọn được khi tạo vị trí mới.')
        : t('Đã bật lại nhóm vị trí.'));
      await load();
    } catch (err: any) {
      // 409 khi nhóm còn vị trí đang dùng — câu của máy chủ đã nói rõ số lượng.
      setError(err.response?.data?.detail || t('Không đổi được trạng thái nhóm vị trí.'));
    }
  };

  return <Box>
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
      <Box>
        <Typography variant="h4" sx={{ fontSize: 22 }}>{t('Quản lý nhóm vị trí')}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t('Nhóm vị trí là sợi dây nối vị trí với thư viện rubric. Nhóm bị tắt không chọn được khi tạo vị trí mới, nhưng dữ liệu cũ giữ nguyên.')}
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button startIcon={<RefreshIcon />} onClick={() => void load()} disabled={loading}>{t('Tải lại')}</Button>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>{t('Thêm nhóm vị trí')}</Button>
      </Box>
    </Box>

    {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
    {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{t(success)}</Alert>}

    {loading ? <CircularProgress /> : <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead><TableRow>
          <TableCell>{t('Mã')}</TableCell>
          <TableCell>{t('Tên')}</TableCell>
          <TableCell align="right">{t('Số vị trí')}</TableCell>
          <TableCell align="right">{t('Số rubric mẫu')}</TableCell>
          <TableCell>{t('Trạng thái')}</TableCell>
          <TableCell align="right">{t('Thao tác')}</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {items.map(item => <TableRow key={item.job_family_id} hover>
            <TableCell><Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{item.code}</Typography></TableCell>
            <TableCell>{item.name}</TableCell>
            <TableCell align="right">{item.position_count}</TableCell>
            <TableCell align="right">{item.template_count}</TableCell>
            <TableCell>
              <Chip size="small" label={item.is_active ? t('Đang hoạt động') : t('Đã tắt')}
                color={item.is_active ? 'success' : 'default'} variant="outlined" />
            </TableCell>
            <TableCell align="right">
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                <Button size="small" onClick={() => openEdit(item)}>{t('Sửa tên')}</Button>
                <Button size="small" color={item.is_active ? 'warning' : 'success'} onClick={() => void toggleActive(item)}>
                  {item.is_active ? t('Tắt') : t('Bật')}
                </Button>
              </Box>
            </TableCell>
          </TableRow>)}
          {!items.length && <TableRow><TableCell colSpan={6}>
            <Typography variant="body2" color="text.secondary">{t('Chưa có nhóm vị trí nào.')}</Typography>
          </TableCell></TableRow>}
        </TableBody>
      </Table>
    </TableContainer>}

    <Dialog open={open} onClose={() => !saving && setOpen(false)} maxWidth="sm" fullWidth>
      <DialogTitle>{editing ? t('Đổi tên nhóm vị trí') : t('Thêm nhóm vị trí')}</DialogTitle>
      <DialogContent>
        {dialogError && <Alert severity="error" sx={{ mb: 2 }}>{t(dialogError)}</Alert>}
        <TextField
          fullWidth required margin="dense" label={t('Mã nhóm')} value={code}
          // Mã bất biến sau khi tạo: nó là khoá nghiệp vụ mà rubric mẫu và báo
          // cáo tham chiếu tới. Đổi mã của nhóm đang dùng là đổi nghĩa dữ liệu cũ.
          disabled={!!editing || saving}
          onChange={event => setCode(event.target.value.toUpperCase())}
          inputProps={{ maxLength: 50 }}
          helperText={editing
            ? t('Mã không đổi được sau khi tạo. Chỉ đổi được tên.')
            : t('Ví dụ IT_DIGITAL. Chỉ chữ, số và gạch dưới; hệ thống tự chuẩn hoá.')}
        />
        <TextField
          fullWidth required margin="dense" label={t('Tên hiển thị')} value={name}
          disabled={saving} onChange={event => setName(event.target.value)}
          inputProps={{ maxLength: 200 }}
          helperText={t('Tên này hiện trong danh sách chọn nhóm khi tạo vị trí và khi tạo rubric mẫu.')}
        />
        {editing && <FormControlLabel sx={{ mt: 1 }}
          control={<Switch checked={editing.is_active} disabled />}
          label={t('Đổi trạng thái bật/tắt ở nút ngoài danh sách, không ở đây.')} />}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setOpen(false)} disabled={saving}>{t('Hủy')}</Button>
        <Button variant="contained" onClick={save} disabled={saving || !name.trim() || (!editing && !code.trim())}>
          {saving ? t('Đang lưu…') : t('Lưu')}
        </Button>
      </DialogActions>
    </Dialog>
  </Box>;
}
