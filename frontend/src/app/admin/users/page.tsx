'use client';

import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, Grid, InputLabel, MenuItem, Paper, Select,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useI18n } from '@/i18n/I18nProvider';
import { adminApi, authApi } from '@/lib/api';

type Role = 'ADMIN' | 'HR_LEAD' | 'HR_RECRUITER' | 'HIRING_MANAGER' | 'VIEWER';
type AccountStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';
type Account = { user_id: string; email: string | null; display_name: string; account_status: AccountStatus; roles: Role[]; must_change_password: boolean };
const roleKeys: Record<Role, string> = {
  ADMIN: 'Quản trị viên', HR_LEAD: 'Trưởng nhóm HR', HR_RECRUITER: 'HR tuyển dụng',
  HIRING_MANAGER: 'Hiring Manager (HM)', VIEWER: 'Người xem',
};
const statusKeys: Record<AccountStatus, string> = { ACTIVE: 'Đang hoạt động', INACTIVE: 'Ngừng hoạt động', SUSPENDED: 'Đã khóa' };
const allRoles = Object.keys(roleKeys) as Role[];
const allStatuses = Object.keys(statusKeys) as AccountStatus[];

export default function AdminUsersPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<Account[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentUser, setCurrentUser] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [roles, setRoles] = useState<Role[]>(['HR_RECRUITER']);
  const [accountStatus, setAccountStatus] = useState<AccountStatus>('ACTIVE');
  const [resetTarget, setResetTarget] = useState<Account | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => { setPage(1); setSearch(searchInput.trim()); }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    Promise.all([
      adminApi.listUsers({ search: search || undefined, role: roleFilter || undefined, account_status: statusFilter || undefined, page }),
      authApi.me(),
    ]).then(([response, me]) => {
      if (active) { setItems(response.data.items); setHasMore(response.data.has_more); setCurrentUser(me.data.user_id); }
    }).catch((err: any) => { if (active) setError(err.response?.data?.detail || t("Không thể tải danh sách tài khoản.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, roleFilter, statusFilter, page, revision, t]);

  const resetForm = () => {
    setOpen(false); setEditing(null); setName(''); setEmail(''); setPassword(''); setConfirm('');
    setRoles(['HR_RECRUITER']); setAccountStatus('ACTIVE'); setDialogError(null);
  };
  const create = () => { resetForm(); setSuccess(null); setOpen(true); };
  const edit = (account: Account) => {
    setEditing(account); setName(account.display_name); setEmail(account.email || ''); setRoles(account.roles);
    setAccountStatus(account.account_status); setPassword(''); setConfirm(''); setDialogError(null); setSuccess(null); setOpen(true);
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setDialogError(null);
    if (!name.trim() || roles.length === 0) { setDialogError(t("Vui lòng nhập họ tên và chọn ít nhất một vai trò.")); return; }
    if (!editing) {
      if (password !== confirm) { setDialogError(t("Mật khẩu xác nhận không khớp.")); return; }
      if ([...password].length < 12 || new TextEncoder().encode(password).length > 72) {
        setDialogError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
      }
    }
    const removed = editing?.roles.filter(role => !roles.includes(role)) || [];
    if (editing && (removed.length > 0 || editing.account_status !== accountStatus) &&
        !window.confirm(t("Thay đổi vai trò hoặc trạng thái có thể ảnh hưởng quyền truy cập và phân công vị trí. Tiếp tục?"))) return;
    const newPrivilegedRole = roles.some(role => ['ADMIN', 'HR_LEAD'].includes(role) && !editing?.roles.includes(role));
    if (newPrivilegedRole && !window.confirm(t("Admin và Trưởng nhóm HR có quyền truy cập rộng. Xác nhận cấp quyền này?"))) return;
    try {
      setSaving(true);
      if (editing) {
        await adminApi.updateUser(editing.user_id, { display_name: name.trim(), account_status: accountStatus, roles });
        setSuccess(t("Đã cập nhật tài khoản."));
      } else {
        await adminApi.createUser({ display_name: name.trim(), email: email.trim(), password, roles });
        setSuccess(t("Đã tạo tài khoản. Hãy chuyển mật khẩu tạm thời qua kênh an toàn; người dùng phải đổi khi đăng nhập."));
      }
      resetForm(); setPage(1); setRevision(value => value + 1);
    } catch (err: any) { setDialogError(err.response?.data?.detail || t("Không thể lưu tài khoản.")); }
    finally { setSaving(false); }
  };
  const openReset = (account: Account) => {
    setResetTarget(account); setResetPassword(''); setResetConfirm(''); setResetError(null); setSuccess(null);
  };
  const closeReset = () => { if (!resetting) { setResetTarget(null); setResetPassword(''); setResetConfirm(''); setResetError(null); } };
  const submitReset = async (event: React.FormEvent) => {
    event.preventDefault(); setResetError(null);
    if (!resetTarget) return;
    if (resetPassword !== resetConfirm) { setResetError(t("Mật khẩu xác nhận không khớp.")); return; }
    if ([...resetPassword].length < 12 || new TextEncoder().encode(resetPassword).length > 72) {
      setResetError(t("Mật khẩu cần ít nhất 12 ký tự và tối đa 72 byte UTF-8.")); return;
    }
    try {
      setResetting(true);
      await adminApi.resetUserPassword(resetTarget.user_id, resetPassword);
      setResetTarget(null); setResetPassword(''); setResetConfirm('');
      setSuccess(t("Đã đặt lại mật khẩu. Hãy chuyển mật khẩu tạm thời qua kênh an toàn; thành viên phải đổi khi đăng nhập lại."));
      setRevision(value => value + 1);
    } catch (err: any) { setResetError(err.response?.data?.detail || t("Không thể đặt lại mật khẩu.")); }
    finally { setResetting(false); }
  };
  const roleChips = (account: Account) => <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
    {account.roles.map(role => <Chip size="small" key={role} label={t(roleKeys[role] || role)} variant="outlined" />)}
  </Box>;

  return <Box>
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 3 }}>
      <Box><Typography variant="h1" sx={{ fontSize: 26, color: '#0A2B57' }}>{t("Quản lý tài khoản")}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{t("Tạo tài khoản và quản lý vai trò, trạng thái truy cập")}</Typography></Box>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => setRevision(value => value + 1)} disabled={loading}>{t("Làm mới")}</Button>
        <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={create}>{t("Tạo tài khoản")}</Button>
      </Box>
    </Box>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
    {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{t(success)}</Alert>}
    <Alert severity="info" sx={{ mb: 3 }}>{t("Việc cấp vai trò HM không tự gán HM vào vị trí; HR phải chọn HM khi tạo vị trí.")}</Alert>
    <Grid container spacing={2} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6}><TextField label={t("Tìm theo tên hoặc email")} value={searchInput} onChange={e => setSearchInput(e.target.value)} fullWidth size="small" /></Grid>
      <Grid item xs={6} sm={3}><FormControl fullWidth size="small"><InputLabel id="role-filter-label">{t("Vai trò")}</InputLabel>
        <Select labelId="role-filter-label" label={t("Vai trò")} value={roleFilter} onChange={e => { setPage(1); setRoleFilter(e.target.value); }}>
          <MenuItem value="">{t("Tất cả vai trò")}</MenuItem>{allRoles.map(role => <MenuItem key={role} value={role}>{t(roleKeys[role])}</MenuItem>)}
        </Select></FormControl></Grid>
      <Grid item xs={6} sm={3}><FormControl fullWidth size="small"><InputLabel id="status-filter-label">{t("Trạng thái")}</InputLabel>
        <Select labelId="status-filter-label" label={t("Trạng thái")} value={statusFilter} onChange={e => { setPage(1); setStatusFilter(e.target.value); }}>
          <MenuItem value="">{t("Tất cả trạng thái")}</MenuItem>{allStatuses.map(status => <MenuItem key={status} value={status}>{t(statusKeys[status])}</MenuItem>)}
        </Select></FormControl></Grid>
    </Grid>
    {loading ? <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" aria-label={t("Đang tải tài khoản")} /></Box> : !error && <>
      {items.length === 0 ? <Paper sx={{ p: 4, textAlign: 'center' }}>{t("Không tìm thấy tài khoản.")}</Paper> : <>
        <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
          {items.map(account => <Card key={account.user_id}><CardContent>
            <Typography fontWeight={700} sx={{ overflowWrap: 'anywhere' }}>{account.display_name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: 'anywhere', mb: 1 }}>{account.email || '—'}</Typography>
            {roleChips(account)}
            <Typography variant="body2" sx={{ mt: 1 }}>{t(statusKeys[account.account_status])}{account.must_change_password ? ` · ${t("Chờ đổi mật khẩu")}` : ''}</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
              <Button onClick={() => edit(account)} aria-label={t("Chỉnh sửa tài khoản {0}", account.display_name)}>{t("Chỉnh sửa")}</Button>
              {account.account_status === 'ACTIVE' && account.user_id !== currentUser && <Button color="warning" onClick={() => openReset(account)} aria-label={t("Đặt lại mật khẩu cho {0}", account.display_name)}>{t("Đặt lại mật khẩu")}</Button>}
            </Box>
          </CardContent></Card>)}
        </Box>
        <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' } }}><Table aria-label={t("Danh sách tài khoản")}>
          <TableHead><TableRow><TableCell>{t("Họ và tên")}</TableCell><TableCell>Email</TableCell><TableCell>{t("Vai trò")}</TableCell><TableCell>{t("Trạng thái")}</TableCell><TableCell align="right">{t("Thao tác")}</TableCell></TableRow></TableHead>
          <TableBody>{items.map(account => <TableRow key={account.user_id}>
            <TableCell>{account.display_name}{account.user_id === currentUser && <Typography variant="caption" display="block" color="text.secondary">{t("Tài khoản của bạn")}</Typography>}</TableCell>
            <TableCell sx={{ overflowWrap: 'anywhere' }}>{account.email || '—'}</TableCell><TableCell>{roleChips(account)}</TableCell>
            <TableCell>{t(statusKeys[account.account_status])}{account.must_change_password && <Typography variant="caption" display="block" color="text.secondary">{t("Chờ đổi mật khẩu")}</Typography>}</TableCell>
            <TableCell align="right"><Box sx={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 1 }}>
              <Button onClick={() => edit(account)} aria-label={t("Chỉnh sửa tài khoản {0}", account.display_name)}>{t("Chỉnh sửa")}</Button>
              {account.account_status === 'ACTIVE' && account.user_id !== currentUser && <Button color="warning" onClick={() => openReset(account)} aria-label={t("Đặt lại mật khẩu cho {0}", account.display_name)}>{t("Đặt lại mật khẩu")}</Button>}
            </Box></TableCell>
          </TableRow>)}</TableBody>
        </Table></TableContainer>
      </>}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1, mt: 2 }}>
        <Button disabled={page <= 1} onClick={() => setPage(value => value - 1)}>{t("Trang trước")}</Button>
        <Typography variant="body2">{t("Trang {0}", page)}</Typography>
        <Button disabled={!hasMore} onClick={() => setPage(value => value + 1)}>{t("Trang sau")}</Button>
      </Box>
    </>}

    <Dialog open={open} onClose={() => { if (!saving) resetForm(); }} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={save}>
        <DialogTitle>{editing ? t("Chỉnh sửa tài khoản") : t("Tạo tài khoản")}</DialogTitle>
        <DialogContent dividers>
          {dialogError && <Alert severity="error" sx={{ mb: 2 }}>{t(dialogError)}</Alert>}
          {!editing && <Alert severity="info" sx={{ mb: 2 }}>{t("Xác minh đúng email và chuyển mật khẩu tạm thời qua kênh an toàn. Người dùng bắt buộc đổi mật khẩu khi đăng nhập lần đầu.")}</Alert>}
          {editing && <Alert severity="warning" sx={{ mb: 2 }}>{t("Bỏ vai trò HR/HM sẽ thu hồi phân công vị trí tương ứng; cấp lại vai trò không tự khôi phục phân công. Tạm khóa giữ phân công để dùng khi kích hoạt lại.")}</Alert>}
          {editing?.user_id === currentUser && <Alert severity="info" sx={{ mb: 2 }}>{t("Bạn không thể tự khóa tài khoản hoặc tự bỏ quyền Admin.")}</Alert>}
          <TextField label={t("Họ và tên")} value={name} onChange={e => setName(e.target.value)} fullWidth required margin="normal" inputProps={{ maxLength: 120 }} />
          <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} fullWidth required margin="normal" disabled={Boolean(editing)} autoComplete="off" />
          {!editing && <>
            <TextField label={t("Mật khẩu tạm thời")} type="password" value={password} onChange={e => setPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
            <TextField label={t("Xác nhận mật khẩu")} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
          </>}
          <FormControl fullWidth required margin="normal"><InputLabel id="edit-roles-label">{t("Vai trò")}</InputLabel>
            <Select labelId="edit-roles-label" multiple value={roles} label={t("Vai trò")} onChange={e => setRoles(e.target.value as Role[])}
              renderValue={selected => selected.map(role => t(roleKeys[role])).join(', ')}>
              {allRoles.map(role => <MenuItem key={role} value={role}>{t(roleKeys[role])}</MenuItem>)}
            </Select></FormControl>
          {editing && <FormControl fullWidth margin="normal"><InputLabel id="edit-status-label">{t("Trạng thái")}</InputLabel>
            <Select labelId="edit-status-label" value={accountStatus} label={t("Trạng thái")} onChange={e => setAccountStatus(e.target.value as AccountStatus)}>
              {allStatuses.map(status => <MenuItem key={status} value={status}>{t(statusKeys[status])}</MenuItem>)}
            </Select></FormControl>}
          {(roles.includes('ADMIN') || roles.includes('HR_LEAD')) && <Alert severity="warning" sx={{ mt: 2 }}>{t("Admin và Trưởng nhóm HR có quyền truy cập rộng; chỉ cấp cho người được ủy quyền.")}</Alert>}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}><Button onClick={resetForm} disabled={saving}>{t("Hủy")}</Button>
          <Button type="submit" variant="contained" color="secondary" disabled={saving}>{saving ? <CircularProgress size={20} color="inherit" /> : t("Lưu tài khoản")}</Button>
        </DialogActions>
      </Box>
    </Dialog>

    <Dialog open={Boolean(resetTarget)} onClose={closeReset} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={submitReset}>
        <DialogTitle>{t("Đặt lại mật khẩu")}</DialogTitle>
        <DialogContent dividers>
          {resetError && <Alert severity="error" sx={{ mb: 2 }}>{t(resetError)}</Alert>}
          <Alert severity="warning" sx={{ mb: 2 }}>{t("Thành viên sẽ phải đổi mật khẩu này khi đăng nhập lại; các phiên đăng nhập hiện tại của thành viên sẽ bị thu hồi.")}</Alert>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{resetTarget ? `${resetTarget.display_name} · ${resetTarget.email || '—'}` : ''}</Typography>
          <TextField label={t("Mật khẩu tạm thời")} type="password" value={resetPassword} onChange={e => setResetPassword(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" helperText={t("Ít nhất 12 ký tự, tối đa 72 byte UTF-8.")} />
          <TextField label={t("Xác nhận mật khẩu")} type="password" value={resetConfirm} onChange={e => setResetConfirm(e.target.value)} fullWidth required margin="normal" autoComplete="new-password" />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}><Button onClick={closeReset} disabled={resetting}>{t("Hủy")}</Button>
          <Button type="submit" variant="contained" color="secondary" disabled={resetting}>{resetting ? <CircularProgress size={20} color="inherit" /> : t("Đặt lại mật khẩu")}</Button>
        </DialogActions>
      </Box>
    </Dialog>
  </Box>;
}
