'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, rubricApi } from '@/lib/api';
import type { JobFamily, RubricTemplateSummary } from '@/types';

type StatusFilter = 'ALL' | 'PUBLISHED' | 'DRAFT_ONLY';

export default function RubricLibraryPage() {
  const { t, dateLocale } = useI18n();
  const router = useRouter();
  const [roles, setRoles] = useState<string[]>([]);
  const [families, setFamilies] = useState<JobFamily[]>([]);
  const [templates, setTemplates] = useState<RubricTemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [familyFilter, setFamilyFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ job_family_id: '', title: '', level_band: '' });
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [familyDialog, setFamilyDialog] = useState<null | { mode: 'create' } | { mode: 'edit'; family: JobFamily }>(null);
  const [familyForm, setFamilyForm] = useState({ code: '', name: '', description: '', status: 'ACTIVE' as JobFamily['status'] });
  const [familyError, setFamilyError] = useState<string | null>(null);
  const [savingFamily, setSavingFamily] = useState(false);

  const canManageFamilies = roles.includes('ADMIN') || roles.includes('HR_LEAD');
  const canCreateTemplates = roles.includes('HR_LEAD') || roles.includes('HR_RECRUITER');

  const loadTemplates = useCallback(async () => {
    const res = await rubricApi.listTemplates({
      job_family_id: familyFilter || undefined, status: statusFilter, q: search.trim() || undefined,
    });
    setTemplates(res.data || []);
  }, [familyFilter, statusFilter, search]);

  const loadFamilies = useCallback(async (manage: boolean) => {
    const res = await rubricApi.listFamilies(manage);
    setFamilies(res.data || []);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const me = await authApi.me();
        const systemRoles: string[] = me.data.system_roles || [];
        setRoles(systemRoles);
        await loadFamilies(systemRoles.includes('ADMIN') || systemRoles.includes('HR_LEAD'));
        setError(null);
      } catch (err: any) {
        setError(err.response?.data?.detail || t("Không thể tải thư viện rubric"));
      } finally { setLoading(false); }
    })();
  }, [loadFamilies, t]);

  useEffect(() => {
    if (loading) return;
    const timer = setTimeout(() => {
      loadTemplates().catch((err: any) => setError(err.response?.data?.detail || t("Không thể tải danh sách template")));
    }, 250);
    return () => clearTimeout(timer);
  }, [loadTemplates, loading, t]);

  const activeFamilies = families.filter(f => f.status === 'ACTIVE');

  const handleCreateTemplate = async () => {
    if (!createForm.job_family_id || !createForm.title.trim() || creating) return;
    try {
      setCreating(true); setCreateError(null);
      const res = await rubricApi.createTemplate({
        job_family_id: createForm.job_family_id, title: createForm.title.trim(), level_band: createForm.level_band.trim() || null,
      });
      setCreateOpen(false);
      router.push(`/rubric-library/templates/${res.data.template_id}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setCreateError(typeof detail === 'string' ? detail : t("Không thể tạo template"));
    } finally { setCreating(false); }
  };

  const openFamilyDialog = (family?: JobFamily) => {
    setFamilyError(null);
    if (family) {
      setFamilyForm({ code: family.code, name: family.name, description: family.description || '', status: family.status });
      setFamilyDialog({ mode: 'edit', family });
    } else {
      setFamilyForm({ code: '', name: '', description: '', status: 'ACTIVE' });
      setFamilyDialog({ mode: 'create' });
    }
  };

  const saveFamily = async () => {
    if (!familyDialog || savingFamily) return;
    try {
      setSavingFamily(true); setFamilyError(null);
      if (familyDialog.mode === 'create') {
        await rubricApi.createFamily({ code: familyForm.code.trim().toUpperCase(), name: familyForm.name.trim(),
          description: familyForm.description.trim() || null });
      } else {
        await rubricApi.updateFamily(familyDialog.family.job_family_id, { name: familyForm.name.trim(),
          description: familyForm.description.trim() || null, status: familyForm.status });
      }
      setFamilyDialog(null);
      await loadFamilies(true);
      await loadTemplates();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setFamilyError(typeof detail === 'string' ? detail : t("Không thể lưu nhóm ngành"));
    } finally { setSavingFamily(false); }
  };

  if (loading) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Thư viện rubric")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Bộ tiêu chí mẫu theo nhóm ngành. HR soạn bản nháp, HR Lead xuất bản; áp dụng vào vị trí vẫn cần HR và Hiring Manager duyệt.")}</Typography>
        </Box>
        {canCreateTemplates && (
          <Button variant="contained" color="secondary" startIcon={<AddIcon />} onClick={() => {
            setCreateError(null); setCreateForm({ job_family_id: familyFilter || activeFamilies[0]?.job_family_id || '', title: '', level_band: '' }); setCreateOpen(true);
          }}>{t("Tạo template")}</Button>
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>{t(error)}</Alert>}

      <Card variant="outlined" sx={{ mb: 3 }}><CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="h4" sx={{ fontSize: 16 }}>{t("Nhóm ngành")}</Typography>
          {canManageFamilies && <Button size="small" startIcon={<AddIcon />} onClick={() => openFamilyDialog()}>{t("Thêm nhóm ngành")}</Button>}
        </Box>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {families.map(family => (
            <Chip key={family.job_family_id}
              label={`${family.name} · ${family.template_count ?? 0}`}
              color={familyFilter === family.job_family_id ? 'secondary' : 'default'}
              variant={family.status === 'ACTIVE' ? 'filled' : 'outlined'}
              onClick={() => setFamilyFilter(current => current === family.job_family_id ? '' : family.job_family_id)}
              onDelete={canManageFamilies ? () => openFamilyDialog(family) : undefined}
              deleteIcon={canManageFamilies ? <EditOutlinedIcon aria-label={t("Sửa nhóm ngành")} /> : undefined}
              sx={family.status === 'INACTIVE' ? { textDecoration: 'line-through' } : undefined} />
          ))}
        </Box>
      </CardContent></Card>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField size="small" label={t("Tìm theo tên template")} value={search} onChange={e => setSearch(e.target.value)}
          sx={{ minWidth: 260, flex: 1, maxWidth: 420 }} inputProps={{ maxLength: 200 }} />
        <TextField size="small" select label={t("Trạng thái xuất bản")} value={statusFilter} sx={{ minWidth: 200 }}
          onChange={e => setStatusFilter(e.target.value as StatusFilter)}>
          <MenuItem value="ALL">{t("Tất cả")}</MenuItem>
          <MenuItem value="PUBLISHED">{t("Đã xuất bản")}</MenuItem>
          <MenuItem value="DRAFT_ONLY">{t("Chưa xuất bản")}</MenuItem>
        </TextField>
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách template rubric")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Template")}</TableCell>
              <TableCell>{t("Nhóm ngành")}</TableCell>
              <TableCell>{t("Cấp bậc")}</TableCell>
              <TableCell>{t("Phiên bản xuất bản")}</TableCell>
              <TableCell>{t("Bản nháp")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {templates.length === 0 ? (
              <TableRow><TableCell colSpan={6} align="center" sx={{ py: 6, color: 'text.secondary' }}>{t("Chưa có template phù hợp")}</TableCell></TableRow>
            ) : templates.map(template => (
              <TableRow key={template.template_id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>{template.title}</Typography>
                  {template.created_by_name && <Typography variant="caption" color="text.secondary">{t("Tạo bởi")} {template.created_by_name}</Typography>}
                </TableCell>
                <TableCell>{template.job_family_name}</TableCell>
                <TableCell>{template.level_band || '—'}</TableCell>
                <TableCell>
                  {template.published_version_id ? (
                    <Box>
                      <Chip size="small" color="success" label={t("v{0} · {1} tiêu chí", template.published_version_number ?? '', template.published_item_count ?? 0)} />
                      {template.published_at && <Typography variant="caption" display="block" color="text.secondary">{new Date(template.published_at).toLocaleDateString(dateLocale)}</Typography>}
                    </Box>
                  ) : <Chip size="small" label={t("Chưa xuất bản")} />}
                </TableCell>
                <TableCell>{template.draft_version_id ? <Chip size="small" color="warning" label={t("Nháp v{0}", template.draft_version_number ?? '')} /> : '—'}</TableCell>
                <TableCell align="right">
                  <Button size="small" variant="outlined" onClick={() => router.push(`/rubric-library/templates/${template.template_id}`)}>{t("Mở")}</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={createOpen} onClose={() => !creating && setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Tạo template rubric")}</DialogTitle>
        <DialogContent>
          {createError && <Alert severity="error" sx={{ mb: 2 }}>{t(createError)}</Alert>}
          <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>
            <TextField select required label={t("Nhóm ngành")} value={createForm.job_family_id}
              onChange={e => setCreateForm({ ...createForm, job_family_id: e.target.value })}>
              {activeFamilies.map(f => <MenuItem key={f.job_family_id} value={f.job_family_id}>{f.name}</MenuItem>)}
            </TextField>
            <TextField required label={t("Tên template")} value={createForm.title} inputProps={{ maxLength: 200 }}
              onChange={e => setCreateForm({ ...createForm, title: e.target.value })} />
            <TextField label={t("Cấp bậc (tùy chọn)")} value={createForm.level_band} inputProps={{ maxLength: 100 }}
              helperText={t("Ví dụ: Junior, Senior. Dùng để gợi ý template theo cấp bậc của vị trí.")}
              onChange={e => setCreateForm({ ...createForm, level_band: e.target.value })} />
            <Typography variant="caption" color="text.secondary">{t("Template được tạo với phiên bản 1 ở trạng thái nháp. Thêm tiêu chí rồi nhờ HR Lead xuất bản.")}</Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)} disabled={creating}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={handleCreateTemplate}
            disabled={creating || !createForm.job_family_id || !createForm.title.trim()}>{creating ? t("Đang lưu…") : t("Tạo template")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!familyDialog} onClose={() => !savingFamily && setFamilyDialog(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{familyDialog?.mode === 'edit' ? t("Sửa nhóm ngành") : t("Thêm nhóm ngành")}</DialogTitle>
        <DialogContent>
          {familyError && <Alert severity="error" sx={{ mb: 2 }}>{t(familyError)}</Alert>}
          <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>
            <TextField required label={t("Mã nhóm ngành")} value={familyForm.code} disabled={familyDialog?.mode === 'edit'}
              helperText={t("Chữ in hoa, số và dấu gạch dưới; không đổi được sau khi tạo.")} inputProps={{ maxLength: 50 }}
              onChange={e => setFamilyForm({ ...familyForm, code: e.target.value.toUpperCase() })} />
            <TextField required label={t("Tên nhóm ngành")} value={familyForm.name} inputProps={{ maxLength: 200 }}
              onChange={e => setFamilyForm({ ...familyForm, name: e.target.value })} />
            <TextField label={t("Mô tả")} multiline minRows={2} value={familyForm.description} inputProps={{ maxLength: 2000 }}
              onChange={e => setFamilyForm({ ...familyForm, description: e.target.value })} />
            {familyDialog?.mode === 'edit' && (
              <TextField select label={t("Trạng thái")} value={familyForm.status}
                onChange={e => setFamilyForm({ ...familyForm, status: e.target.value as JobFamily['status'] })}
                helperText={t("Nhóm ngừng sử dụng không xóa dữ liệu cũ; chỉ không dùng cho template hoặc vị trí mới.")}>
                <MenuItem value="ACTIVE">{t("Đang dùng")}</MenuItem>
                <MenuItem value="INACTIVE">{t("Ngừng sử dụng")}</MenuItem>
              </TextField>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFamilyDialog(null)} disabled={savingFamily}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={saveFamily}
            disabled={savingFamily || !familyForm.name.trim() || !/^[A-Z][A-Z0-9_]{1,49}$/.test(familyForm.code)}>{savingFamily ? t("Đang lưu…") : t("Lưu")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
