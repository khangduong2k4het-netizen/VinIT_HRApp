'use client';

// F3.05: the wording of letters to candidates. HR sees it; HR Lead and Admin edit it.
import * as React from 'react';
import { useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress, Stack, TextField, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { candidateEmailsApi, type EmailTemplateCode } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type Template = { template_code: EmailTemplateCode; name: string; subject_template: string; body_template: string; updated_at: string };

const VARIABLE_HELP: Record<string, string> = {
  ho_ten: 'Họ tên ứng viên', vi_tri: 'Tên vị trí', ma_vi_tri: 'Mã vị trí', ngay_nop: 'Ngày nộp hồ sơ',
  ten_hr: 'Tên HR gửi thư', email_hr: 'Email HR gửi thư', thoi_gian_pv: 'Thời gian phỏng vấn (HR nhập khi gửi)',
  dia_diem_pv: 'Địa điểm phỏng vấn (HR nhập khi gửi)',
};

export default function EmailTemplatesPage() {
  const { t, dateLocale } = useI18n();
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [edits, setEdits] = useState<Record<string, { subject: string; body: string }>>({});
  const [canEdit, setCanEdit] = useState(false);
  const [variables, setVariables] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    candidateEmailsApi.templates().then(res => {
      setTemplates(res.data.templates); setCanEdit(res.data.can_edit); setVariables(res.data.variables);
      setEdits(Object.fromEntries(res.data.templates.map((tpl: Template) => [tpl.template_code, { subject: tpl.subject_template, body: tpl.body_template }])));
    }).catch((err: any) => { setError(err.response?.data?.detail || t('Không thể tải mẫu thư.')); setTemplates([]); });
  }, [t]);

  const save = async (code: EmailTemplateCode) => {
    const edit = edits[code];
    if (!edit || saving) return;
    try {
      setSaving(code); setError(null); setSaved(null);
      const res = await candidateEmailsApi.updateTemplate(code, { subject_template: edit.subject, body_template: edit.body });
      setTemplates(prev => (prev || []).map(tpl => tpl.template_code === code ? res.data : tpl));
      setSaved(code);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể lưu mẫu thư.'));
    } finally { setSaving(null); }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>{t('Mẫu thư ứng viên')}</Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        {t('Khi HR soạn thư, hệ thống điền sẵn nội dung theo mẫu; HR vẫn sửa được từng thư trước khi gửi. Chỉ HR Lead và Admin sửa được mẫu.')}
      </Alert>
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('Biến dùng được trong tiêu đề và nội dung')}</Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {variables.map(name => <Chip key={name} size="small" variant="outlined" label={`{${name}} · ${t(VARIABLE_HELP[name] || name)}`} />)}
        </Stack>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
      {templates === null ? <CircularProgress size={24} /> : templates.map(tpl => {
        const edit = edits[tpl.template_code] || { subject: tpl.subject_template, body: tpl.body_template };
        const changed = edit.subject !== tpl.subject_template || edit.body !== tpl.body_template;
        return (
          <Accordion key={tpl.template_code} disableGutters elevation={0}
            sx={{ mb: 1.5, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box>
                <Typography fontWeight={600}>{t(tpl.name)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('Cập nhật')}: {new Date(tpl.updated_at).toLocaleString(dateLocale)}
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <TextField fullWidth size="small" label={t('Tiêu đề')} value={edit.subject} sx={{ mb: 2 }}
                InputProps={{ readOnly: !canEdit }} inputProps={{ maxLength: 300 }}
                onChange={e => setEdits(prev => ({ ...prev, [tpl.template_code]: { ...edit, subject: e.target.value } }))} />
              <TextField fullWidth multiline minRows={10} label={t('Nội dung')} value={edit.body}
                InputProps={{ readOnly: !canEdit }} inputProps={{ maxLength: 10000 }}
                onChange={e => setEdits(prev => ({ ...prev, [tpl.template_code]: { ...edit, body: e.target.value } }))} />
              {canEdit && (
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }} alignItems="center">
                  <Button variant="contained" color="secondary" size="small" onClick={() => save(tpl.template_code)}
                    disabled={!changed || !edit.subject.trim() || !edit.body.trim() || saving === tpl.template_code}>
                    {saving === tpl.template_code ? <CircularProgress size={16} color="inherit" /> : t('Lưu mẫu')}
                  </Button>
                  <Button size="small" disabled={!changed}
                    onClick={() => setEdits(prev => ({ ...prev, [tpl.template_code]: { subject: tpl.subject_template, body: tpl.body_template } }))}>
                    {t('Bỏ thay đổi')}
                  </Button>
                  {saved === tpl.template_code && !changed && <Typography variant="caption" color="success.main">{t('Đã lưu mẫu.')}</Typography>}
                </Stack>
              )}
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Box>
  );
}
