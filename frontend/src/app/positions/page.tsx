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
import LinkIcon from '@mui/icons-material/Link';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { positionsApi, usersApi, dashboardApi, authApi, departmentsApi, rubricApi, criteriaApi } from '@/lib/api';
import { useScrollMemory, useUrlState } from '@/lib/navMemory';
import PageHeader from '@/components/common/PageHeader';
import EmptyState from '@/components/common/EmptyState';
import StatusBadge from '@/components/common/StatusBadge';
import { Department, JobFamily, Position, UserSummary } from '@/types';

const renderDepartmentCode = (codeFormat: string, sequence: number) =>
  codeFormat.replace(/\{SEQ(?::(0+))?\}/, (_match, zeros: string | undefined) =>
    String(sequence).padStart((zeros || '').length || 1, '0'));

export default function PositionsPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  // Kept in the URL (?q=&status=) so Back and the sidebar reopen the same filtered list.
  const [search, setSearch] = useUrlState<string>('q', '');
  const [statusFilter, setStatusFilter] = useUrlState<'ALL' | Position['status']>('status', 'ALL', ['ALL', 'OPEN', 'PAUSED', 'CLOSED']);
  const [families, setFamilies] = useState<JobFamily[]>([]);
  const [loading, setLoading] = useState(true);
  useScrollMemory(!loading);
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
    posting_content: '',
  });
  // Import a JD draft from a public job-posting link.
  const [jdUrl, setJdUrl] = useState('');
  const [jdImporting, setJdImporting] = useState(false);
  const [jdImportError, setJdImportError] = useState<string | null>(null);
  const [jdImportResult, setJdImportResult] = useState<any | null>(null);
  // Title and level the AI filled in from the posting. A field still holding that value
  // is labelled as an AI suggestion and is refreshed by the next import; once HR types
  // something else, an import leaves it alone.
  const [aiFilled, setAiFilled] = useState<{ title: string; level: string; levelInferred: boolean }>({ title: '', level: '', levelInferred: false });
  // F2.01: start the new position's criteria from a published rubric template ('' = later, on the position page).
  type PublishedTemplate = { template_id: string; title: string; level_band: string | null; job_family_id: string;
    job_family_name: string; published_version_id: string | null; published_version_number: number | null; published_item_count: number;
    published_has_jd?: boolean };
  const [publishedTemplates, setPublishedTemplates] = useState<PublishedTemplate[]>([]);
  const [startTemplateVersionId, setStartTemplateVersionId] = useState('');
  // The JD text last filled in from a template's sample JD (to label it and refresh it on another choice).
  const [jdFromTemplate, setJdFromTemplate] = useState('');
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
  // Published templates for the "initial criteria" choice, loaded when the create dialog opens.
  useEffect(() => {
    if (!createDialogOpen) return;
    rubricApi.listTemplates({ status: 'PUBLISHED' })
      .then(res => setPublishedTemplates((res.data || []).filter((tpl: PublishedTemplate) => tpl.published_version_id)))
      .catch(() => setPublishedTemplates([]));
  }, [createDialogOpen]);
  // Same job family first, then same level, then by title.
  const sameLevel = (tpl: PublishedTemplate) => !!formData.level.trim() && (tpl.level_band || '').trim().toLowerCase() === formData.level.trim().toLowerCase();
  const sortedTemplates = [...publishedTemplates].sort((a, b) =>
    Number(b.job_family_id === formData.job_family_id) - Number(a.job_family_id === formData.job_family_id)
    || Number(sameLevel(b)) - Number(sameLevel(a)) || a.title.localeCompare(b.title));
  const startTemplate = publishedTemplates.find(tpl => tpl.published_version_id === startTemplateVersionId);

  // Choosing a template also pre-fills the JD with its sample JD. A JD HR wrote or imported is only
  // replaced after confirmation; a JD that still holds the previous template's sample is refreshed silently.
  const chooseStartTemplate = async (versionId: string) => {
    setStartTemplateVersionId(versionId);
    const tpl = publishedTemplates.find(item => item.published_version_id === versionId);
    if (!versionId || !tpl?.published_has_jd) return;
    try {
      const sample = ((await rubricApi.getVersion(versionId)).data?.jd_template || '').trim();
      if (!sample) return;
      const current = formData.jd_content.trim();
      if (current && current !== jdFromTemplate.trim() && current !== sample
          && !window.confirm(t("Mẫu này có JD mẫu. Thay nội dung JD hiện tại bằng JD mẫu?"))) return;
      setJdFromTemplate(sample);
      setFormData(prev => ({ ...prev, jd_content: sample }));
    } catch { /* the template is still applied; HR writes the JD */ }
  };

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
        ...(formData.posting_content.trim() ? { posting_content: formData.posting_content.trim() } : {}),
      };
      const created = (await positionsApi.create(payload)).data;
      const templateVersionId = startTemplateVersionId;
      setCreateDialogOpen(false);
      setStartTemplateVersionId(''); setJdFromTemplate('');
      setFormData({ department_id: '', title: '', jd_content: '', hiring_manager_user_id: '', job_family_id: '', level: '', posting_content: '' });
      setJdUrl(''); setJdImportResult(null); setJdImportError(null); setAiFilled({ title: '', level: '', levelInferred: false });
      setHmSelectedName('');
      setHmSearchQuery('');
      setHmOptions([]);
      if (templateVersionId && created?.position_id) {
        // The template becomes a criteria DRAFT; HR and the Hiring Manager still approve it on the position page.
        try {
          await criteriaApi.applyTemplate(created.position_id, templateVersionId);
        } catch (err: any) {
          const detail = err.response?.data?.detail;
          setError(t("Đã tạo vị trí {0} nhưng chưa áp dụng được mẫu: {1}. Bạn có thể áp dụng lại bằng nút \"Áp dụng từ thư viện\" trên trang vị trí.",
            created.position_code || '', typeof detail === 'string' ? t(detail) : t("lỗi không xác định")));
          await loadPositions();
          return;
        }
        router.push(`/positions/${created.position_id}`);
        return;
      }
      await loadPositions();
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || t("Không thể tạo vị trí mới"));
    } finally {
      setCreateLoading(false);
    }
  };

  const handleImportJd = async () => {
    const url = jdUrl.trim();
    if (!url || jdImporting) return;
    if (formData.jd_content.trim() && !window.confirm(t("Nội dung JD hiện tại sẽ được thay bằng JD lấy từ đường dẫn. Tiếp tục?"))) return;
    try {
      setJdImporting(true); setJdImportError(null); setJdImportResult(null);
      const res = await positionsApi.importJd(url);
      const data = res.data;
      const aiTitle = (data.title || '').trim();
      const aiLevel = (data.level || '').trim();
      const replaceable = (current: string, previousAi: string) => !current.trim() || current === previousAi;
      const keptTitle = !!aiTitle && !replaceable(formData.title, aiFilled.title) && formData.title.trim() !== aiTitle;
      const keptLevel = !!aiLevel && !replaceable(formData.level, aiFilled.level) && formData.level.trim() !== aiLevel;
      setFormData(prev => ({
        ...prev,
        jd_content: data.jd_content || prev.jd_content,
        posting_content: data.posting_content || prev.posting_content,
        title: aiTitle && replaceable(prev.title, aiFilled.title) ? aiTitle : prev.title,
        level: aiLevel && replaceable(prev.level, aiFilled.level) ? aiLevel : prev.level,
      }));
      setAiFilled({ title: aiTitle, level: aiLevel, levelInferred: data.level_basis === 'INFERRED' });
      setJdImportResult({ ...data, keptTitle, keptLevel });
    } catch (err: any) {
      setJdImportError(err.response?.data?.detail || t("Không lấy được JD từ đường dẫn này"));
    } finally {
      setJdImporting(false);
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
      <PageHeader
        eyebrow={t('Tuyển dụng')}
        title={t("Danh sách vị trí tuyển dụng")}
        description={t("Quản lý các vị trí đang tuyển, tiêu chí đánh giá và hồ sơ ứng viên")}
        actions={canCreate ? (
          <Button
            variant="contained"
            color="secondary"
            startIcon={<AddIcon />}
            onClick={() => { setCreateError(null); setCreateDialogOpen(true); }}
          >{t("Tạo vị trí mới")}</Button>
        ) : undefined}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={loadPositions}>{t("Thử lại")}</Button>}>
          {t(error)}
        </Alert>
      )}

      {!error && <>
      {/* Summary Cards */}
      <Grid container spacing={{ xs: 2, sm: 2.5 }} sx={{ mb: 3 }}>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">{t("Vị trí đang mở")}</Typography>
              <Typography variant="h3" className="tabular-nums" sx={{ fontSize: 26, fontWeight: 700, color: 'primary.main', mt: 0.75 }}>
                {positions.filter(p => p.status === 'OPEN').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">{t("Tạm dừng")}</Typography>
              <Typography variant="h3" className="tabular-nums" sx={{ fontSize: 26, fontWeight: 700, color: 'warning.main', mt: 0.75 }}>
                {positions.filter(p => p.status === 'PAUSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">{t("Đã đóng")}</Typography>
              <Typography variant="h3" className="tabular-nums" sx={{ fontSize: 26, fontWeight: 700, color: 'text.secondary', mt: 0.75 }}>
                {positions.filter(p => p.status === 'CLOSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card variant="outlined">
            <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
              <Typography variant="caption" color="text.secondary">{t("Tổng hồ sơ")}</Typography>
              <Typography variant="h3" className="tabular-nums" sx={{ fontSize: 26, fontWeight: 700, color: 'primary.main', mt: 0.75 }}>
                {applicationTotal ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* S-03: search by title/code and filter by position status. */}
      <Card variant="outlined" sx={{ mb: 2.5 }}>
        <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 }, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField size="small" label={t("Tìm theo tên hoặc mã vị trí")} value={search}
            onChange={e => setSearch(e.target.value)} sx={{ minWidth: 260, flex: 1, maxWidth: 440 }} inputProps={{ maxLength: 200 }} />
          <TextField size="small" select label={t("Trạng thái")} value={statusFilter} sx={{ minWidth: 180 }}
            onChange={e => setStatusFilter(e.target.value as 'ALL' | Position['status'])}>
            <MenuItem value="ALL">{t("Tất cả")}</MenuItem>
            <MenuItem value="OPEN">{t("Đang mở")}</MenuItem>
            <MenuItem value="PAUSED">{t("Tạm dừng")}</MenuItem>
            <MenuItem value="CLOSED">{t("Đã đóng")}</MenuItem>
          </TextField>
          <Typography variant="caption" color="text.secondary" className="tabular-nums" sx={{ ml: 'auto' }}>
            {visiblePositions.length}/{positions.length}
          </Typography>
        </CardContent>
      </Card>

      {/* On small screens cards keep the actions and status visible without horizontal scrolling. */}
      <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
        {visiblePositions.length === 0 ? (
          <EmptyState title={emptyMessage} />
        ) : visiblePositions.map(pos => (
          <Card key={pos.position_id} variant="outlined">
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'primary.main', overflowWrap: 'anywhere' }}>{pos.title}</Typography>
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
      {visiblePositions.length === 0 ? (
        <Box sx={{ display: { xs: 'none', md: 'block' } }}>
          <EmptyState title={emptyMessage} />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 2 }}>
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
              {visiblePositions.map((pos) => (
                <TableRow
                  key={pos.position_id}
                  hover
                  onClick={() => router.push(`/positions/${pos.position_id}`)}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>
                    <Typography variant="body2" className="mono-code" sx={{ fontWeight: 600, color: 'primary.main' }}>
                      {pos.position_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{pos.title}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{pos.department_name || pos.org_unit || '-'}</Typography>
                  </TableCell>
                  <TableCell>{getPositionStatusBadge(pos.status)}</TableCell>
                  <TableCell>
                    {getCriteriaBadge(pos)}
                  </TableCell>
                  <TableCell align="right" onClick={e => e.stopPropagation()}>
                    <IconButton
                      color="primary"
                      onClick={() => router.push(`/positions/${pos.position_id}`)}
                      aria-label={t("Xem vị trí {0}", pos.title)}
                    >
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      </>}

      {/* Create Position Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => { if (!createLoading) setCreateDialogOpen(false); }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ color: 'primary.main', fontWeight: 700 }}>{t("Tạo vị trí tuyển dụng mới")}</DialogTitle>
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
                helperText={formData.title && formData.title === aiFilled.title ? t("AI điền từ tin tuyển dụng, bạn có thể sửa.") : undefined}
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
              <TextField fullWidth label={t("Cấp bậc")} value={formData.level} inputProps={{ maxLength: 100, list: 'position-levels' }}
                onChange={(e) => setFormData({ ...formData, level: e.target.value })} placeholder="Senior"
                helperText={formData.level && formData.level === aiFilled.level
                  ? (aiFilled.levelInferred ? t("Tin không ghi cấp bậc; AI suy ra từ yêu cầu kinh nghiệm. Hãy kiểm tra.") : t("AI điền từ tin tuyển dụng, bạn có thể sửa."))
                  : undefined} />
              <datalist id="position-levels">
                {['Intern', 'Fresher', 'Junior', 'Middle', 'Senior', 'Lead', 'Manager', 'Director'].map(level => <option key={level} value={level} />)}
              </datalist>
            </Grid>
            <Grid item xs={12}>
              <TextField select fullWidth label={t("Bộ tiêu chí ban đầu")} value={startTemplateVersionId}
                onChange={(e) => { void chooseStartTemplate(e.target.value); }}
                SelectProps={{ displayEmpty: true, renderValue: () => startTemplate
                  ? `${startTemplate.title}${startTemplate.level_band ? ` · ${startTemplate.level_band}` : ''}`
                  : t("Để sau: AI đề xuất từ JD hoặc tự soạn trên trang vị trí") }}
                InputLabelProps={{ shrink: true }}
                helperText={startTemplate
                  ? t("Mẫu được sao chép thành bộ tiêu chí nháp cho vị trí; HR và Hiring Manager vẫn phải duyệt trước khi chấm CV.")
                  : publishedTemplates.length
                    ? t("Chọn một mẫu trong thư viện rubric, hoặc để AI đề xuất tiêu chí từ JD trên trang vị trí.")
                    : t("Thư viện rubric chưa có mẫu nào được xuất bản.")}>
                <MenuItem value="">{t("Để sau: AI đề xuất từ JD hoặc tự soạn trên trang vị trí")}</MenuItem>
                {sortedTemplates.map(tpl => (
                  <MenuItem key={tpl.published_version_id!} value={tpl.published_version_id!}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span>{tpl.title}{tpl.level_band ? ` · ${tpl.level_band}` : ''}</span>
                      <Typography component="span" variant="caption" color="text.secondary">
                        {tpl.job_family_name} · {t("{0} tiêu chí", tpl.published_item_count)} · {t("Phiên bản ")}{tpl.published_version_number}
                        {tpl.published_has_jd ? ` · ${t("Có JD mẫu")}` : ''}
                      </Typography>
                      {formData.job_family_id && tpl.job_family_id === formData.job_family_id && <Chip size="small" color="success" label={t("Cùng nhóm ngành")} />}
                      {sameLevel(tpl) && <Chip size="small" color="success" label={t("Cùng cấp bậc")} />}
                    </Box>
                  </MenuItem>
                ))}
              </TextField>
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
              <Box sx={{ p: 2, border: '1px dashed #C9D3E0', borderRadius: 2, backgroundColor: '#F8FAFC' }}>
                <Typography variant="subtitle2" sx={{ color: '#0A2B57', mb: 0.5 }}>{t("Lấy JD từ đường dẫn tin tuyển dụng (tùy chọn)")}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                  {t("Dán link trang tuyển dụng công khai, ví dụ vinuni.talent.vn. Hệ thống đọc trang, AI lọc ra phần mô tả công việc và yêu cầu, rồi điền vào ô JD bên dưới để bạn rà soát.")}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  <TextField size="small" sx={{ flex: 1, minWidth: 260 }} value={jdUrl}
                    onChange={(e) => setJdUrl(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleImportJd(); } }}
                    placeholder="https://vinuni.talent.vn/job/..." inputProps={{ 'aria-label': t("Đường dẫn tin tuyển dụng") }} />
                  <Button variant="outlined" startIcon={jdImporting ? <CircularProgress size={16} /> : <LinkIcon />}
                    onClick={handleImportJd} disabled={jdImporting || !/^https?:\/\/\S+/i.test(jdUrl.trim())}
                    sx={{ borderColor: '#0A2B57', color: '#0A2B57' }}>
                    {jdImporting ? t("Đang lấy JD…") : t("Lấy JD")}
                  </Button>
                </Box>
                {jdImportError && <Alert severity="error" sx={{ mt: 1.5 }}>{t(jdImportError)}</Alert>}
                {jdImportResult && (
                  <Alert severity={jdImportResult.ai_used ? 'info' : 'warning'} sx={{ mt: 1.5 }}>
                    <Typography variant="body2" fontWeight={600}>
                      {jdImportResult.ai_used
                        ? t("Đã lấy JD và AI đã lọc lại nội dung. Hãy đọc kỹ và chỉnh sửa trước khi tạo vị trí.")
                        : t("Đã lấy nguyên văn nội dung trang (AI chưa lọc lại). Hãy tự rút gọn trước khi tạo vị trí.")}
                    </Typography>
                    <Typography variant="caption" sx={{ display: 'block' }}>
                      {t("Nguồn")}: {jdImportResult.final_url}
                      {jdImportResult.metadata?.posting_id ? ` · ${t("Mã tin")}: ${jdImportResult.metadata.posting_id}` : ''}
                      {jdImportResult.metadata?.valid_through ? ` · ${t("Hạn nộp")}: ${jdImportResult.metadata.valid_through}` : ''}
                      {jdImportResult.metadata?.employment_type ? ` · ${jdImportResult.metadata.employment_type}` : ''}
                    </Typography>
                    {(jdImportResult.keptTitle || jdImportResult.keptLevel) && (
                      <Typography variant="caption" sx={{ display: 'block' }}>
                        {t("Giữ nguyên nội dung bạn đã nhập. AI gợi ý:")}
                        {jdImportResult.keptTitle ? ` ${t("Tên vị trí")}: ${jdImportResult.title}` : ''}
                        {jdImportResult.keptTitle && jdImportResult.keptLevel ? ' ·' : ''}
                        {jdImportResult.keptLevel ? ` ${t("Cấp bậc")}: ${jdImportResult.level}` : ''}
                      </Typography>
                    )}
                    {jdImportResult.language_code === 'vi' && (
                      <Typography variant="caption" sx={{ display: 'block' }}>{t("Tin tuyển dụng viết bằng tiếng Việt; JD được giữ nguyên ngôn ngữ gốc.")}</Typography>
                    )}
                    {(jdImportResult.notes || []).length > 0 && (
                      <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
                        {jdImportResult.notes.map((note: string, i: number) => (
                          <li key={i}><Typography variant="caption">{note}</Typography></li>
                        ))}
                      </Box>
                    )}
                  </Alert>
                )}
              </Box>
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
                helperText={jdFromTemplate && formData.jd_content.trim() === jdFromTemplate.trim()
                  ? t("JD mẫu điền từ thư viện rubric; hãy chỉnh lại cho vị trí này.")
                  : t("Sau khi tạo, bạn có thể yêu cầu AI đề xuất bản nháp tiêu chí từ JD")}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label={t("Nội dung đăng tuyển (hiện cho ứng viên)")}
                fullWidth
                multiline
                rows={5}
                inputProps={{ maxLength: 20000 }}
                value={formData.posting_content}
                onChange={(e) => setFormData({ ...formData, posting_content: e.target.value })}
                helperText={t("Giới thiệu, quyền lợi, hạn nộp… Hiện cùng JD trên trang tuyển dụng; không dùng để chấm điểm.")}
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
