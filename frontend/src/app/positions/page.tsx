'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Autocomplete,
  Tooltip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { positionsApi, usersApi, dashboardApi, authApi, departmentsApi, rubricApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { Department, JobFamily, Position, UserSummary } from '@/types';

const renderDepartmentCode = (codeFormat: string, sequence: number) =>
  codeFormat.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) =>
    String(sequence).padStart((zeros || '').length || 1, '0'));

export default function PositionsPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | Position['status']>('ALL');
  const [families, setFamilies] = useState<JobFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [applicationTotal, setApplicationTotal] = useState<number | null>(null);
  const [canCreate, setCanCreate] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentsLoading, setDepartmentsLoading] = useState(false);
  const [formData, setFormData] = useState({
    department_id: '',
    title: '',
    jd_content: '',
    hiring_manager_user_id: '',
    job_family_id: '',
    level: '',
  });
  const [hmSearchQuery, setHmSearchQuery] = useState('');
  const [hmOptions, setHmOptions] = useState<UserSummary[]>([]);
  const [hmLoading, setHmLoading] = useState(false);
  const [hmSelectedName, setHmSelectedName] = useState('');
  const selectedDepartment = departments.find((department) => department.department_id === formData.department_id);
  const positionCodePreview = selectedDepartment
    ? renderDepartmentCode(selectedDepartment.code_format, selectedDepartment.next_sequence)
    : '';

  const loadPositions = useCallback(async () => {
    try {
      setLoading(true);
      const [positions, stats, me] = await Promise.all([
        positionsApi.listAll(), dashboardApi.getSummary().catch(() => null), authApi.me(),
      ]);
      const mayCreate = me.data.system_roles?.some((role: string) => ['ADMIN', 'HR_LEAD', 'HR_RECRUITER'].includes(role)) ||
        me.data.position_assignments?.some((a: any) => ['HR_RECRUITER', 'HR_LEAD'].includes(a.position_role)) || false;
      setCanCreate(mayCreate);
      setPositions(positions);
      setError(null);
      // Job families (F2.01) only feed the create dialog; HM accounts cannot read them,
      // so don't ask (it was a 403 on every visit).
      if (mayCreate) rubricApi.listFamilies().then(res => setFamilies(res.data || [])).catch(() => setFamilies([]));
      setApplicationTotal(stats?.data?.total_applications ?? null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải danh sách vị trí"));
    } finally {
      setLoading(false);
    }
  }, [t]);
  useEffect(() => { loadPositions(); }, [loadPositions]);

  const handleCreatePosition = async () => {
    try {
      setCreateLoading(true); setCreateError(null);
      const payload = {
        department_id: formData.department_id,
        title: formData.title,
        jd_content: formData.jd_content,
        hiring_manager_user_id: formData.hiring_manager_user_id,
        ...(formData.job_family_id ? { job_family_id: formData.job_family_id } : {}),
        ...(formData.level.trim() ? { level: formData.level.trim() } : {}),
      };
      await positionsApi.create(payload);
      setCreateDialogOpen(false);
      setFormData({ department_id: '', title: '', jd_content: '', hiring_manager_user_id: '', job_family_id: '', level: '' });
      setHmSelectedName('');
      setHmSearchQuery('');
      setHmOptions([]);
      await loadPositions();
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || t("Không thể tạo vị trí mới"));
    } finally {
      setCreateLoading(false);
    }
  };

  // Preload the department dropdown and the Hiring Manager list as soon as
  // the create dialog opens, so both choices are visible without typing.
  useEffect(() => {
    if (!createDialogOpen) return;
    let active = true;
    setDepartmentsLoading(true);
    setHmLoading(true);
    Promise.allSettled([
      departmentsApi.list(false),
      usersApi.list({ role: 'HIRING_MANAGER' }),
    ]).then(([departmentResult, hmResult]) => {
      if (!active) return;
      if (departmentResult.status === 'fulfilled') {
        setDepartments(departmentResult.value.data || []);
      } else {
        setDepartments([]);
        setCreateError(departmentResult.reason?.response?.data?.detail || t("Không thể tải danh sách phòng ban."));
      }
      if (hmResult.status === 'fulfilled') {
        setHmOptions(hmResult.value.data || []);
      } else {
        setHmOptions([]);
      }
    }).finally(() => {
      if (active) {
        setDepartmentsLoading(false);
        setHmLoading(false);
      }
    });
    return () => { active = false; };
  }, [createDialogOpen, t]);

  const getPositionStatusBadge = (status: string) => {
    switch (status) {
      case 'OPEN':
        return <StatusBadge type="position-open" label={t("Đang mở")} />;
      case 'PAUSED':
        return <StatusBadge type="position-paused" label={t("Tạm dừng")} />;
      case 'CLOSED':
        return <StatusBadge type="position-closed" label={t("Đã đóng")} />;
      default:
        return null;
    }
  };

  const getCriteriaBadge = (pos: Position) => {
    const labels: Record<string, string> = {
      DRAFT: t("Bản nháp"), PENDING_HR_REVIEW: t("Chờ HR duyệt"),
      PENDING_HM_APPROVAL: t("Chờ HM duyệt"), APPROVED: t("Đã duyệt"), REJECTED: t("Từ chối"),
    };
    const label = pos.criteria_status ? (labels[pos.criteria_status] || t("Chưa rõ")) : t("Chưa có");
    const description = pos.criteria_approved && pos.criteria_status !== 'APPROVED'
      ? t("Phiên bản mới nhất chưa hoàn tất; vẫn có phiên bản trước đã duyệt.")
      : t("Trạng thái của phiên bản tiêu chí mới nhất");
    return (
      <Tooltip title={description}>
        <span><StatusBadge type={pos.criteria_status === 'APPROVED' ? 'criteria-approved' : 'criteria-draft'} label={label} /></span>
      </Tooltip>
    );
  };

  const searchTerm = search.trim().toLowerCase();
  const visiblePositions = positions.filter(p =>
    (statusFilter === 'ALL' || p.status === statusFilter) &&
    (!searchTerm || p.title.toLowerCase().includes(searchTerm) || p.position_code.toLowerCase().includes(searchTerm)));
  const emptyMessage = positions.length === 0 ? t("Chưa có vị trí trong phạm vi của bạn") : t("Không có vị trí phù hợp với bộ lọc");

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 4 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Danh sách vị trí tuyển dụng")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Quản lý các vị trí đang tuyển, tiêu chí đánh giá và hồ sơ ứng viên")}</Typography>
        </Box>
        {canCreate && <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => { setCreateError(null); setCreateDialogOpen(true); }}
          size="large"
        >{t("Tạo vị trí mới")}</Button>}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={loadPositions}>{t("Thử lại")}</Button>}>
          {t(error)}
        </Alert>
      )}

      {!error && <>
      {/* Summary Cards */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 4 }}>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Vị trí đang mở")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {positions.filter(p => p.status === 'OPEN').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Tạm dừng")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#B54708', mt: 1 }}>
                {positions.filter(p => p.status === 'PAUSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Đã đóng")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#475569', mt: 1 }}>
                {positions.filter(p => p.status === 'CLOSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Tổng hồ sơ")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {applicationTotal ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* S-03: search by title/code and filter by position status. */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField size="small" label={t("Tìm theo tên hoặc mã vị trí")} value={search}
          onChange={e => setSearch(e.target.value)} sx={{ minWidth: 260, flex: 1, maxWidth: 420 }} inputProps={{ maxLength: 200 }} />
        <TextField size="small" select label={t("Trạng thái")} value={statusFilter} sx={{ minWidth: 180 }}
          onChange={e => setStatusFilter(e.target.value as 'ALL' | Position['status'])}>
          <MenuItem value="ALL">{t("Tất cả")}</MenuItem>
          <MenuItem value="OPEN">{t("Đang mở")}</MenuItem>
          <MenuItem value="PAUSED">{t("Tạm dừng")}</MenuItem>
          <MenuItem value="CLOSED">{t("Đã đóng")}</MenuItem>
        </TextField>
      </Box>

      {/* On small screens cards keep the actions and status visible without horizontal scrolling. */}
      <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
        {visiblePositions.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>{emptyMessage}</Paper>
        ) : visiblePositions.map(pos => (
          <Card key={pos.position_id} sx={{ border: '1px solid #E9EEF4' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0A2B57', overflowWrap: 'anywhere' }}>{pos.title}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{pos.position_code} · {pos.department_name || pos.org_unit || t("Chưa có đơn vị")}</Typography>
                </Box>
                {getPositionStatusBadge(pos.status)}
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 2 }}>
                <Box><Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>{t("Tiêu chí mới nhất")}</Typography>{getCriteriaBadge(pos)}</Box>
                <Button variant="outlined" size="small" onClick={() => router.push(`/positions/${pos.position_id}`)} aria-label={t("Xem vị trí {0}", pos.title)}>{t("Xem vị trí")}</Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {/* Wider screens retain the compact table. */}
      <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách vị trí tuyển dụng")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Mã vị trí")}</TableCell>
              <TableCell>{t("Tên vị trí")}</TableCell>
              <TableCell>{t("Đơn vị")}</TableCell>
              <TableCell>{t("Trạng thái")}</TableCell>
              <TableCell>{t("Tiêu chí mới nhất")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visiblePositions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary' }}>{emptyMessage}</TableCell>
              </TableRow>
            ) : (
              visiblePositions.map((pos) => (
                <TableRow key={pos.position_id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                      {pos.position_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>{pos.title}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{pos.department_name || pos.org_unit || '-'}</Typography>
                  </TableCell>
                  <TableCell>{getPositionStatusBadge(pos.status)}</TableCell>
                  <TableCell>
                    {getCriteriaBadge(pos)}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      color="primary"
                      onClick={() => router.push(`/positions/${pos.position_id}`)}
                      sx={{ color: '#0A2B57' }}
                      aria-label={t("Xem vị trí {0}", pos.title)}
                    >
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      </>}

      {/* Create Position Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => { if (!createLoading) setCreateDialogOpen(false); }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: '#0A2B57', fontWeight: 'bold' }}>{t("Tạo vị trí tuyển dụng mới")}</DialogTitle>
        <DialogContent dividers>
          {createError && <Alert severity="error" sx={{ mb: 2 }}>{t(createError)}</Alert>}
          <Grid container spacing={3} sx={{ pt: 1 }}>
            <Grid item xs={12}>
              <FormControl fullWidth required>
                <InputLabel id="create-position-department-label">{t("Đơn vị / Phòng ban")}</InputLabel>
                <Select
                  labelId="create-position-department-label"
                  label={t("Đơn vị / Phòng ban")}
                  value={formData.department_id}
                  onChange={(e) => setFormData({ ...formData, department_id: e.target.value })}
                  disabled={departmentsLoading}
                >
                  {departments.map((department) => (
                    <MenuItem key={department.department_id} value={department.department_id}>
                      {department.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {departmentsLoading && <Typography variant="caption" color="text.secondary">{t("Đang tải danh sách phòng ban...")}</Typography>}
              {!departmentsLoading && departments.length === 0 && (
                <Alert severity="warning" sx={{ mt: 1 }}>{t("Chưa có phòng ban đang hoạt động. Admin cần tạo phòng ban trước.")}</Alert>
              )}
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label={t("Mã vị trí (tự sinh)")}
                fullWidth
                value={positionCodePreview}
                placeholder={t("Chọn phòng ban để sinh mã")}
                helperText={selectedDepartment
                  ? t("Sinh theo mã định dạng {0}", selectedDepartment.code_format)
                  : t("Mã được sinh theo mã định dạng của phòng ban, ví dụ REQ-IT-001")}
                InputProps={{ readOnly: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label={t("Tên vị trí")}
                fullWidth
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Senior Software Engineer"
              />
            </Grid>
            <Grid item xs={12} sm={7}>
              <TextField select fullWidth label={t("Nhóm ngành")} value={formData.job_family_id}
                onChange={(e) => setFormData({ ...formData, job_family_id: e.target.value })}
                helperText={t("Dùng để gợi ý template rubric phù hợp.")}>
                <MenuItem value="">{t("Chưa chọn")}</MenuItem>
                {families.map(f => <MenuItem key={f.job_family_id} value={f.job_family_id}>{f.name}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={5}>
              <TextField fullWidth label={t("Cấp bậc")} value={formData.level} inputProps={{ maxLength: 100 }}
                onChange={(e) => setFormData({ ...formData, level: e.target.value })} placeholder="Senior" />
            </Grid>
            <Grid item xs={12}>
              <Autocomplete
                options={hmOptions}
                loading={hmLoading}
                getOptionLabel={(opt: any) => typeof opt === 'string' ? opt : opt.display_name || ''}
                isOptionEqualToValue={(opt: any, val: any) => opt.user_id === val?.user_id}
                inputValue={hmSearchQuery}
                onInputChange={(_, val) => setHmSearchQuery(val)}
                noOptionsText={t("Không tìm thấy Hiring Manager đang hoạt động")}
                value={hmOptions.find((option) => option.user_id === formData.hiring_manager_user_id)
                  || (formData.hiring_manager_user_id ? { user_id: formData.hiring_manager_user_id, display_name: hmSelectedName } as UserSummary : null)}
                onChange={(_, val: any) => {
                  if (val && typeof val === 'object') {
                    setFormData({ ...formData, hiring_manager_user_id: val.user_id });
                    setHmSelectedName(val.display_name);
                  } else {
                    setFormData({ ...formData, hiring_manager_user_id: '' });
                    setHmSelectedName('');
                  }
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Hiring Manager" required
                    placeholder={t("Chọn Hiring Manager")}
                    helperText={t("Danh sách Hiring Manager đang hoạt động đã tải sẵn; nhập tên để lọc nhanh. Chỉ chọn HM khác tài khoản HR; người này sẽ duyệt chuyên môn.")}
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {hmLoading ? <CircularProgress size={16} /> : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t("Nội dung Job Description (tiếng Anh)")}
                fullWidth
                required
                multiline
                rows={10}
                value={formData.jd_content}
                onChange={(e) => setFormData({ ...formData, jd_content: e.target.value })}
                placeholder="Paste full JD content here..."
                helperText={t("Sau khi tạo, bạn có thể yêu cầu AI đề xuất bản nháp tiêu chí từ JD")}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 3 }}>
          <Button onClick={() => setCreateDialogOpen(false)} color="inherit">{t("Hủy")}</Button>
          <Button
            onClick={handleCreatePosition}
            variant="contained"
            color="secondary"
            disabled={createLoading || !formData.department_id || !formData.title.trim() || !formData.jd_content.trim() || !formData.hiring_manager_user_id}
          >
            {createLoading ? <CircularProgress size={20} color="inherit" /> : t("Tạo vị trí")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
