'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Breadcrumbs, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Divider, Grid, Link as MuiLink, List, ListItem, MenuItem, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import PublishIcon from '@mui/icons-material/Publish';
import ArchiveOutlinedIcon from '@mui/icons-material/ArchiveOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { authApi, rubricApi } from '@/lib/api';
import type { RubricTemplateDetail, RubricTemplateVersion, TemplateItem, TemplateItemInput } from '@/types';

type ItemForm = TemplateItemInput & { template_item_id?: string; keywordsText: string };

const STATUS_LABEL: Record<string, string> = { DRAFT: 'Bản nháp', PUBLISHED: 'Đã xuất bản', ARCHIVED: 'Đã lưu trữ' };
const STATUS_COLOR: Record<string, 'warning' | 'success' | 'default'> = { DRAFT: 'warning', PUBLISHED: 'success', ARCHIVED: 'default' };

export default function RubricTemplatePage() {
  const { t, dateLocale } = useI18n();
  const params = useParams();
  const templateId = params.id as string;
  const [template, setTemplate] = useState<RubricTemplateDetail | null>(null);
  const [version, setVersion] = useState<RubricTemplateVersion | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [me, setMe] = useState<{ user_id: string; system_roles: string[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [itemForm, setItemForm] = useState<ItemForm | null>(null);
  const [itemError, setItemError] = useState<string | null>(null);
  const [weightOpen, setWeightOpen] = useState(false);
  const [mandatoryWeight, setMandatoryWeight] = useState('70');
  const [reviewAction, setReviewAction] = useState<null | 'PUBLISH' | 'ARCHIVE'>(null);
  const [reviewComment, setReviewComment] = useState('');
  const [newVersionOpen, setNewVersionOpen] = useState(false);
  const [changeNote, setChangeNote] = useState('');

  const roles = me?.system_roles || [];
  const isLead = roles.includes('HR_LEAD');
  const isDraft = version?.status === 'DRAFT';
  const canEdit = !!version && isDraft && (isLead || (roles.includes('HR_RECRUITER') && version.created_by === me?.user_id));
  const canCreateVersion = (isLead || roles.includes('HR_RECRUITER')) && !template?.draft_version_id;

  const loadVersion = useCallback(async (versionId: string) => {
    const res = await rubricApi.getVersion(versionId);
    setVersion(res.data);
  }, []);

  const loadAll = useCallback(async (preferVersionId?: string) => {
    try {
      const [templateRes, meRes] = await Promise.all([rubricApi.getTemplate(templateId), authApi.me()]);
      setMe({ user_id: meRes.data.user_id, system_roles: meRes.data.system_roles || [] });
      const detail: RubricTemplateDetail = templateRes.data;
      setTemplate(detail);
      const target = preferVersionId || detail.draft_version_id || detail.published_version_id || detail.versions[0]?.template_version_id;
      if (target) { setSelectedVersionId(target); await loadVersion(target); }
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải template"));
    } finally { setLoading(false); }
  }, [templateId, loadVersion, t]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const run = async (action: () => Promise<unknown>, fallback: string, after?: () => Promise<void>) => {
    if (busy) return false;
    try {
      setBusy(true); setError(null);
      await action();
      if (after) await after(); else await loadAll(selectedVersionId);
      return true;
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t(fallback));
      return false;
    } finally { setBusy(false); }
  };

  const openItem = (item?: TemplateItem, category: TemplateItem['category'] = 'MUST_HAVE') => {
    setItemError(null);
    setItemForm(item ? {
      template_item_id: item.template_item_id, name: item.name, description: item.description, category: item.category,
      weight_in_group: Number(item.weight_in_group), expected_evidence_keywords: item.expected_evidence_keywords || [],
      evidence_guidance: item.evidence_guidance || '', keywordsText: (item.expected_evidence_keywords || []).join(', '),
    } : { name: '', description: '', category, weight_in_group: 0, expected_evidence_keywords: [], evidence_guidance: '', keywordsText: '' });
  };

  const saveItem = async () => {
    if (!itemForm || !version || busy) return;
    const payload: TemplateItemInput = {
      name: itemForm.name.trim(), description: itemForm.description.trim(), category: itemForm.category,
      weight_in_group: Number(itemForm.weight_in_group),
      expected_evidence_keywords: itemForm.keywordsText.split(',').map(k => k.trim()).filter(Boolean),
      evidence_guidance: itemForm.evidence_guidance?.trim() || null,
    };
    try {
      setBusy(true); setItemError(null);
      if (itemForm.template_item_id) await rubricApi.updateItem(itemForm.template_item_id, payload);
      else await rubricApi.addItem(version.template_version_id, payload);
      setItemForm(null);
      await loadVersion(version.template_version_id);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setItemError(typeof detail === 'string' ? detail : t("Không thể lưu tiêu chí"));
    } finally { setBusy(false); }
  };

  const weightValue = Number(mandatoryWeight);
  const validWeight = /^\d{1,3}(?:\.\d{0,2})?$/.test(mandatoryWeight) && weightValue > 0 && weightValue <= 100;

  const groupSum = (category: TemplateItem['category']) =>
    (version?.items || []).filter(i => i.category === category).reduce((sum, i) => sum + Number(i.weight_in_group), 0);

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;
  if (!template) return <Alert severity="error">{t(error || "Không tìm thấy template")}</Alert>;

  const renderGroup = (category: TemplateItem['category'], label: string, total?: number) => {
    const items = (version?.items || []).filter(i => i.category === category);
    const sum = groupSum(category);
    return (
      <Card variant="outlined" sx={{ height: '100%' }}><CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="h4" sx={{ fontSize: 16 }}>{t(label)} ({total ?? 0}%)</Typography>
          <Chip size="small" color={items.length === 0 || Math.abs(sum - 100) < 0.001 ? 'default' : 'warning'}
            label={t("Tổng trong nhóm: {0}%", Math.round(sum * 100) / 100)} />
        </Box>
        <Divider sx={{ mb: 1 }} />
        <List disablePadding>
          {items.length === 0 && <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>{t("Chưa có tiêu chí")}</Typography>}
          {items.map((item, idx) => (
            <ListItem key={item.template_item_id} sx={{ px: 0, flexDirection: 'column', alignItems: 'flex-start' }}>
              <Box sx={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                <Typography variant="body2" fontWeight={600}>{idx + 1}. {item.name}</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                  <Chip size="small" label={`${item.weight_in_group}%`} sx={{ height: 20, fontSize: 11 }} />
                  {canEdit && <>
                    <Button size="small" startIcon={<EditOutlinedIcon />} onClick={() => openItem(item)}>{t("Sửa")}</Button>
                    <Button size="small" color="error" startIcon={<DeleteOutlineIcon />}
                      onClick={() => run(() => rubricApi.deleteItem(item.template_item_id), "Không thể xóa tiêu chí",
                        () => loadVersion(item.template_version_id))}>{t("Xóa")}</Button>
                  </>}
                </Box>
              </Box>
              <Typography variant="body2" color="text.secondary">{item.description}</Typography>
              {item.evidence_guidance && <Typography variant="caption" color="text.secondary">{t("Hướng dẫn bằng chứng:")} {item.evidence_guidance}</Typography>}
              {item.expected_evidence_keywords?.length > 0 && (
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                  {item.expected_evidence_keywords.map(k => <Chip key={k} label={k} size="small" variant="outlined" sx={{ height: 20, fontSize: 11 }} />)}
                </Box>
              )}
            </ListItem>
          ))}
        </List>
        {canEdit && <Button size="small" startIcon={<AddIcon />} sx={{ mt: 1 }} onClick={() => openItem(undefined, category)}>{t("Thêm tiêu chí")}</Button>}
      </CardContent></Card>
    );
  };

  return (
    <Box>
      <Breadcrumbs sx={{ mb: 2 }}>
        <MuiLink component={Link} href="/rubric-library" color="inherit">{t("Thư viện rubric")}</MuiLink>
        <Typography color="text.primary">{template.title}</Typography>
      </Breadcrumbs>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{template.title}</Typography>
          <Typography variant="body2" color="text.secondary">{template.job_family_name}{template.level_band ? ` · ${template.level_band}` : ''}</Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TextField select size="small" label={t("Phiên bản")} value={selectedVersionId} sx={{ minWidth: 220 }}
            onChange={async e => { setSelectedVersionId(e.target.value); await loadVersion(e.target.value); }}>
            {template.versions.map(v => (
              <MenuItem key={v.template_version_id} value={v.template_version_id}>
                {t("Phiên bản ")}{v.version_number} · {t(STATUS_LABEL[v.status])}
              </MenuItem>
            ))}
          </TextField>
          {canCreateVersion && <Button variant="outlined" startIcon={<ContentCopyIcon />} onClick={() => { setChangeNote(''); setNewVersionOpen(true); }}>{t("Tạo phiên bản mới")}</Button>}
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}

      {version && <>
        <Card variant="outlined" sx={{ mb: 2 }}><CardContent sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 0.5 }}>
              <Typography variant="subtitle1" fontWeight={700}>{t("Phiên bản ")}{version.version_number}</Typography>
              <Chip size="small" color={STATUS_COLOR[version.status]} label={t(STATUS_LABEL[version.status])} />
            </Box>
            <Typography variant="body2" color="text.secondary">
              {t("Bắt buộc")} {version.mandatory_weight_total}% · {t("Ưu tiên")} {version.nice_to_have_weight_total}%
              {version.created_by_name ? ` · ${t("Tạo bởi")} ${version.created_by_name}` : ''}
              {version.published_at ? ` · ${t("Xuất bản")} ${new Date(version.published_at).toLocaleDateString(dateLocale)}${version.published_by_name ? ` (${version.published_by_name})` : ''}` : ''}
            </Typography>
            {version.change_note && <Typography variant="body2" sx={{ mt: 0.5 }}>{t("Ghi chú thay đổi:")} {version.change_note}</Typography>}
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'flex-start' }}>
            {canEdit && <Button startIcon={<EditOutlinedIcon />} onClick={() => { setMandatoryWeight(String(version.mandatory_weight_total)); setWeightOpen(true); }}>{t("Điều chỉnh trọng số")}</Button>}
            {isLead && isDraft && <Button variant="contained" color="secondary" startIcon={<PublishIcon />} disabled={busy || version.publish_errors.length > 0}
              onClick={() => { setReviewComment(''); setReviewAction('PUBLISH'); }}>{t("Xuất bản")}</Button>}
            {isLead && version.status !== 'ARCHIVED' && <Button color="inherit" startIcon={<ArchiveOutlinedIcon />} disabled={busy}
              onClick={() => { setReviewComment(''); setReviewAction('ARCHIVE'); }}>{isDraft ? t("Hủy bản nháp") : t("Lưu trữ")}</Button>}
          </Box>
        </CardContent></Card>

        {isDraft && version.publish_errors.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2" fontWeight={600}>{t("Chưa đủ điều kiện xuất bản:")}</Typography>
            {version.publish_errors.map(message => <Typography key={message} variant="body2">• {message}</Typography>)}
          </Alert>
        )}
        {isDraft && version.publish_errors.length === 0 && !isLead && (
          <Alert severity="info" sx={{ mb: 2 }}>{t("Bản nháp đã đủ điều kiện. Nhờ HR Lead xuất bản để áp dụng cho các vị trí.")}</Alert>
        )}
        {version.status === 'PUBLISHED' && <Alert severity="success" sx={{ mb: 2 }}>{t("Phiên bản đang được dùng để áp dụng vào vị trí. Phiên bản đã xuất bản không sửa được; hãy tạo phiên bản mới.")}</Alert>}

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} md={6}>{renderGroup('MUST_HAVE', 'Tiêu chí bắt buộc', version.mandatory_weight_total)}</Grid>
          <Grid item xs={12} md={6}>{renderGroup('NICE_TO_HAVE', 'Tiêu chí ưu tiên', version.nice_to_have_weight_total)}</Grid>
        </Grid>

        {version.review_events.length > 0 && (
          <Card variant="outlined"><CardContent>
            <Typography variant="h4" sx={{ fontSize: 16, mb: 1 }}>{t("Lịch sử xuất bản")}</Typography>
            {version.review_events.map(event => (
              <Box key={event.event_id} sx={{ py: 1, borderTop: '1px solid #EDF1F5' }}>
                <Typography variant="body2" fontWeight={600}>
                  {event.reviewer_name || 'HR Lead'} · {{ PUBLISH: t("Xuất bản"), ARCHIVE: t("Lưu trữ"), REQUEST_CHANGES: t("Yêu cầu chỉnh sửa") }[event.decision]}
                </Typography>
                <Typography variant="caption">{new Date(event.decided_at).toLocaleString(dateLocale)}</Typography>
                {event.comment && <Typography variant="body2" color="text.secondary">{event.comment}</Typography>}
              </Box>
            ))}
          </CardContent></Card>
        )}
      </>}

      <Dialog open={!!itemForm} onClose={() => !busy && setItemForm(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{itemForm?.template_item_id ? t("Chỉnh sửa tiêu chí") : t("Thêm tiêu chí")}</DialogTitle>
        <DialogContent>
          {itemError && <Alert severity="error" sx={{ mb: 2 }}>{t(itemError)}</Alert>}
          {itemForm && <Box sx={{ display: 'grid', gap: 2, pt: 1 }}>
            <TextField required label={t("Tên tiêu chí")} value={itemForm.name} inputProps={{ maxLength: 200 }}
              onChange={e => setItemForm({ ...itemForm, name: e.target.value })} />
            <TextField required multiline minRows={3} label={t("Mô tả")} value={itemForm.description} inputProps={{ maxLength: 4000 }}
              onChange={e => setItemForm({ ...itemForm, description: e.target.value })} />
            <TextField select label={t("Nhóm tiêu chí")} value={itemForm.category}
              onChange={e => setItemForm({ ...itemForm, category: e.target.value as TemplateItem['category'] })}>
              <MenuItem value="MUST_HAVE">{t("Bắt buộc")}</MenuItem>
              <MenuItem value="NICE_TO_HAVE">{t("Ưu tiên")}</MenuItem>
            </TextField>
            <TextField type="number" label={t("Trọng số tương đối trong nhóm (%)")} value={itemForm.weight_in_group}
              inputProps={{ min: 0, max: 100, step: 0.1 }} helperText={t("Tổng trọng số các tiêu chí trong mỗi nhóm phải bằng 100% khi xuất bản.")}
              onChange={e => setItemForm({ ...itemForm, weight_in_group: Number(e.target.value) })} />
            <TextField label={t("Từ khóa bằng chứng")} value={itemForm.keywordsText} helperText={t("Phân tách bằng dấu phẩy, tối đa 20 từ khóa.")}
              onChange={e => setItemForm({ ...itemForm, keywordsText: e.target.value })} />
            <TextField multiline minRows={2} label={t("Hướng dẫn xác định bằng chứng")} value={itemForm.evidence_guidance || ''} inputProps={{ maxLength: 4000 }}
              onChange={e => setItemForm({ ...itemForm, evidence_guidance: e.target.value })} />
            <Typography variant="caption" color="text.secondary">{t("Không dùng tuổi, giới tính, ngoại hình, hôn nhân, tính cách hoặc “phù hợp văn hóa” làm tiêu chí.")}</Typography>
          </Box>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setItemForm(null)} disabled={busy}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" onClick={saveItem}
            disabled={busy || !itemForm?.name.trim() || !itemForm?.description.trim() || (itemForm?.weight_in_group ?? -1) < 0 || (itemForm?.weight_in_group ?? 101) > 100}>
            {busy ? t("Đang lưu…") : t("Lưu tiêu chí")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={weightOpen} onClose={() => !busy && setWeightOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t("Điều chỉnh trọng số nhóm")}</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth sx={{ mt: 1 }} type="number" label={t("Nhóm bắt buộc (%)")} value={mandatoryWeight}
            onChange={e => setMandatoryWeight(e.target.value)} error={mandatoryWeight !== '' && !validWeight}
            helperText={t("Nhập lớn hơn 0 và tối đa 100, với tối đa 2 chữ số thập phân.")} />
          <Typography variant="body2" sx={{ mt: 2 }}>{t("Nhóm ưu tiên: ")}<strong>{validWeight ? `${Math.round((100 - weightValue) * 100) / 100}%` : '—'}</strong></Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWeightOpen(false)} disabled={busy}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" disabled={busy || !validWeight || !version}
            onClick={async () => {
              if (!version) return;
              const ok = await run(() => rubricApi.updateVersion(version.template_version_id, {
                mandatory_weight_total: weightValue, nice_to_have_weight_total: Math.round((100 - weightValue) * 100) / 100,
              }), "Không thể lưu trọng số", () => loadVersion(version.template_version_id));
              if (ok) setWeightOpen(false);
            }}>{t("Lưu trọng số")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!reviewAction} onClose={() => !busy && setReviewAction(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{reviewAction === 'PUBLISH' ? t("Xuất bản phiên bản này?") : t("Lưu trữ phiên bản này?")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {reviewAction === 'PUBLISH'
              ? t("Phiên bản đang xuất bản (nếu có) sẽ tự chuyển sang lưu trữ. Bộ tiêu chí đã áp dụng vào vị trí trước đó không bị thay đổi.")
              : t("Phiên bản lưu trữ không còn được gợi ý cho vị trí mới. Bộ tiêu chí đã áp dụng trước đó không bị thay đổi.")}
          </Typography>
          <TextField fullWidth multiline minRows={2} label={t("Ghi chú (tùy chọn)")} value={reviewComment}
            onChange={e => setReviewComment(e.target.value)} inputProps={{ maxLength: 2000 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReviewAction(null)} disabled={busy}>{t("Hủy")}</Button>
          <Button variant="contained" color={reviewAction === 'PUBLISH' ? 'secondary' : 'inherit'} disabled={busy || !version}
            onClick={async () => {
              if (!version) return;
              const ok = await run(() => reviewAction === 'PUBLISH'
                ? rubricApi.publish(version.template_version_id, reviewComment.trim())
                : rubricApi.archive(version.template_version_id, reviewComment.trim()),
              reviewAction === 'PUBLISH' ? "Không thể xuất bản" : "Không thể lưu trữ");
              if (ok) setReviewAction(null);
            }}>{t("Xác nhận")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={newVersionOpen} onClose={() => !busy && setNewVersionOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Tạo phiên bản mới")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{t("Bản nháp mới sao chép toàn bộ tiêu chí và trọng số từ phiên bản đang chọn.")}</Typography>
          <TextField fullWidth multiline minRows={2} label={t("Ghi chú thay đổi")} value={changeNote}
            onChange={e => setChangeNote(e.target.value)} inputProps={{ maxLength: 2000 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewVersionOpen(false)} disabled={busy}>{t("Hủy")}</Button>
          <Button variant="contained" color="secondary" disabled={busy}
            onClick={async () => {
              let created = '';
              const ok = await run(async () => {
                const res = await rubricApi.createVersion(templateId, { source_version_id: selectedVersionId || undefined, change_note: changeNote.trim() || null });
                created = res.data.template_version_id;
              }, "Không thể tạo phiên bản mới", async () => { await loadAll(created); });
              if (ok) setNewVersionOpen(false);
            }}>{t("Tạo bản nháp")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
