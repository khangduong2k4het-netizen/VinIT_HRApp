'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useRef, useState } from 'react';
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, Grid, InputLabel, MenuItem, Select, TextField, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { applicationsApi } from '@/lib/api';

type FactType = 'EDUCATION' | 'WORK_EXPERIENCE' | 'SKILL' | 'CERTIFICATION' | 'LANGUAGE' | 'PROJECT';
type Fact = { fact_type: FactType; fact_value: Record<string, unknown>; source_page_number: number | null };
type Profile = { profile_version_id: string | null; version_number: number; identity: { display_name?: string | null; email?: string | null; phone?: string | null }; facts: Fact[] };
type DraftField = { key: string; value: string; kind: 'text' | 'json' };
type DraftFact = { fact_type: FactType; fields: DraftField[]; source_page_number: number | null };

const factLabels: Record<FactType, string> = {
  EDUCATION: 'Học vấn', WORK_EXPERIENCE: 'Kinh nghiệm làm việc', SKILL: 'Kỹ năng',
  CERTIFICATION: 'Chứng chỉ', LANGUAGE: 'Ngôn ngữ', PROJECT: 'Dự án',
};
const fieldLabels: Record<string, string> = {
  name: 'Tên', title: 'Chức danh', role: 'Vai trò', company: 'Đơn vị', employer: 'Đơn vị',
  institution: 'Cơ sở đào tạo', school: 'Trường', degree: 'Bằng cấp', field: 'Chuyên ngành',
  description: 'Mô tả', year: 'Năm', start_date: 'Bắt đầu', end_date: 'Kết thúc',
  page_number: 'Trang nguồn', level: 'Trình độ', issuer: 'Đơn vị cấp',
};
const presets: Record<FactType, string[]> = {
  EDUCATION: ['institution', 'degree', 'field'], WORK_EXPERIENCE: ['company', 'role', 'description'],
  SKILL: ['name'], CERTIFICATION: ['name', 'issuer'], LANGUAGE: ['name', 'level'], PROJECT: ['name', 'description'],
};

function toDraft(fact: Fact): DraftFact {
  return { fact_type: fact.fact_type, source_page_number: fact.source_page_number,
    fields: Object.entries(fact.fact_value || {}).map(([key, value]) => ({
      key, value: typeof value === 'string' ? value : JSON.stringify(value), kind: typeof value === 'string' ? 'text' : 'json',
    })) };
}

export default function CandidateProfilePanel({ applicationId, canEdit, onSaved }: { applicationId: string; canEdit: boolean; onSaved: () => void }) {
  const { t } = useI18n();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [facts, setFacts] = useState<DraftFact[]>([]);
  const [newType, setNewType] = useState<FactType>('SKILL');
  const [message, setMessage] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  // Profile ứng viên là accordion đóng sẵn, nằm dưới phần tiêu chí. Tải nó ngay
  // khi mở hồ sơ chỉ làm chậm màn hình đầu bằng một request cho khối chưa ai
  // mở; nạp ở lần mở đầu tiên, sau đó giữ nguyên.
  const loadedOnce = useRef(false);

  const load = useCallback(async () => {
    try { setLoading(true); setError(null); setProfile((await applicationsApi.getProfile(applicationId)).data); }
    catch (err: any) { setError(err.response?.data?.detail || t("Không thể tải profile ứng viên.")); }
    finally { setLoading(false); }
  }, [applicationId, t]);

  const edit = () => {
    if (!profile) return;
    setName(profile.identity.display_name || ''); setEmail(profile.identity.email || ''); setPhone(profile.identity.phone || '');
    setFacts(profile.facts.map(toDraft)); setError(null); setOpen(true);
  };
  const changeField = (factIndex: number, fieldIndex: number, value: string) => {
    setFacts(current => current.map((fact, i) => i !== factIndex ? fact : {
      ...fact, source_page_number: null, fields: fact.fields.map((field, j) => j === fieldIndex ? { ...field, value } : field),
    }));
  };
  const save = async () => {
    if (!profile || !name.trim()) { setError(t("Vui lòng nhập tên ứng viên.")); return; }
    try {
      const structured = facts.map(fact => ({ fact_type: fact.fact_type, source_page_number: fact.source_page_number,
        fact_value: Object.fromEntries(fact.fields.map(field => [field.key, field.kind === 'json' ? JSON.parse(field.value) : field.value])) }));
      setSaving(true); setError(null);
      const response = await applicationsApi.updateProfile(applicationId, { expected_profile_version_id: profile.profile_version_id,
        display_name: name.trim(), email: email.trim() || null, phone: phone.trim() || null, facts: structured });
      setProfile(response.data); setOpen(false);
      setMessage(t("Đã lưu phiên bản profile. Đánh giá cũ không còn hiện hành; hãy chạy lại đánh giá và chia sẻ lại shortlist nếu cần."));
      onSaved();
    } catch (err: any) {
      setError(err instanceof SyntaxError ? t("Một trường dữ liệu có cấu trúc chưa đúng JSON.") : (err.response?.data?.detail || t("Không thể lưu profile.")));
    } finally { setSaving(false); }
  };

  return <>
    <Accordion
      disableGutters
      elevation={0}
      expanded={expanded}
      onChange={(_event, next) => { setExpanded(next); if (next && !loadedOnce.current) { loadedOnce.current = true; void load(); } }}
      sx={{ mb: 2, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography fontWeight={600}>{t("Profile ứng viên ")}{profile?.version_number ? t("· phiên bản {0}", profile.version_number) : ''}</Typography></AccordionSummary>
      <AccordionDetails>
        {loading ? <CircularProgress size={22} /> : error && !open ? <Alert severity="error" action={<Button onClick={() => { loadedOnce.current = true; void load(); }}>{t("Thử lại")}</Button>}>{t(error)}</Alert> : profile && <>
          {message && <Alert severity="info" sx={{ mb: 2 }} onClose={() => setMessage(null)}>{t(message)}</Alert>}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <Typography variant="body2" color="text.secondary">{profile.identity.email || t("Chưa có email")} · {profile.identity.phone || t("Chưa có số điện thoại")}</Typography>
            {canEdit && <Button size="small" variant="outlined" onClick={edit}>{t("Chỉnh sửa profile")}</Button>}
          </Box>
          {!profile.facts.length ? <Typography variant="body2" color="text.secondary">{t("Chưa có thông tin chuyên môn được lưu.")}</Typography> : profile.facts.map((fact, index) => <Box key={index} sx={{ borderTop: '1px solid #EDF1F5', py: 1 }}>
            <Typography variant="body2" fontWeight={600}>{t(factLabels[fact.fact_type])}</Typography>
            {Object.entries(fact.fact_value || {}).map(([key, value]) => <Typography key={key} variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              <Box component="span" sx={{ color: 'text.secondary' }}>{fieldLabels[key] ? t(fieldLabels[key]) : key}: </Box>{typeof value === 'string' ? value : JSON.stringify(value)}
            </Typography>)}
          </Box>)}
        </>}
      </AccordionDetails>
    </Accordion>
    <Dialog open={open} onClose={() => !saving && setOpen(false)} maxWidth="md" fullWidth>
      <DialogTitle>{t("Chỉnh sửa profile ứng viên")}</DialogTitle>
      <DialogContent dividers>
        <Alert severity="info" sx={{ mb: 2 }}>{t("Bản cũ được giữ lại. Sau khi lưu, chạy lại đánh giá; kết quả và shortlist cũ không tự cập nhật. Ghi chú nội bộ không được gửi cho AI.")}</Alert>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
        <Grid container spacing={2}>
          <Grid item xs={12}><TextField fullWidth required label={t("Tên ứng viên")} value={name} onChange={e => setName(e.target.value)} inputProps={{ maxLength: 200 }} /></Grid>
          <Grid item xs={12} sm={6}><TextField fullWidth label="Email" value={email} onChange={e => setEmail(e.target.value)} inputProps={{ maxLength: 320 }} /></Grid>
          <Grid item xs={12} sm={6}><TextField fullWidth label={t("Điện thoại")} value={phone} onChange={e => setPhone(e.target.value)} inputProps={{ maxLength: 60 }} /></Grid>
        </Grid>
        <Typography variant="h5" sx={{ mt: 3, mb: 1 }}>{t("Thông tin chuyên môn")}</Typography>
        {facts.map((fact, index) => <Box key={index} sx={{ border: '1px solid #E4E7EC', borderRadius: 1, p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, mb: 1 }}><Typography fontWeight={600}>{t(factLabels[fact.fact_type])}</Typography>
            <Button color="error" size="small" onClick={() => setFacts(current => current.filter((_, i) => i !== index))}>{t("Xóa mục")}</Button></Box>
          <Grid container spacing={2}>{fact.fields.map((field, fieldIndex) => <Grid item xs={12} sm={field.key === 'description' ? 12 : 6} key={field.key}>
            <TextField fullWidth size="small" multiline={field.key === 'description' || field.kind === 'json'} minRows={field.kind === 'json' ? 2 : 1}
              label={fieldLabels[field.key] ? t(fieldLabels[field.key]) : field.key} value={field.value} onChange={e => changeField(index, fieldIndex, e.target.value)}
              helperText={field.kind === 'json' ? t("Dữ liệu có cấu trúc, giữ định dạng JSON") : undefined} />
          </Grid>)}</Grid>
        </Box>)}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 200 }}><InputLabel id="profile-fact-type-label">{t("Loại thông tin")}</InputLabel><Select labelId="profile-fact-type-label" label={t("Loại thông tin")} value={newType} onChange={e => setNewType(e.target.value as FactType)}>
            {Object.entries(factLabels).map(([key, label]) => <MenuItem key={key} value={key}>{t(label)}</MenuItem>)}
          </Select></FormControl>
          <Button variant="outlined" onClick={() => setFacts(current => [...current, { fact_type: newType, source_page_number: null,
            fields: presets[newType].map(key => ({ key, value: '', kind: 'text' })) }])}>{t("Thêm mục")}</Button>
        </Box>
      </DialogContent>
      <DialogActions><Button onClick={() => setOpen(false)} disabled={saving}>{t("Hủy")}</Button><Button variant="contained" onClick={save} disabled={saving || !name.trim()}>{t("Lưu phiên bản mới")}</Button></DialogActions>
    </Dialog>
  </>;
}
