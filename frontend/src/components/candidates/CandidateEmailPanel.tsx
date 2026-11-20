'use client';

// F3.05: letters to this candidate (drafts, recorded and sent) and a way to write one.
import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress, Collapse, Stack, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import { candidateEmailsApi, type EmailTemplateCode } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import CandidateEmailDialog, { COMPOSE_TEMPLATES, type EmailDraft } from './CandidateEmailDialog';

type EmailRow = EmailDraft & {
  status: 'DRAFT' | 'RECORDED' | 'SENT' | 'FAILED' | 'CANCELLED';
  trigger_source: string; created_at: string; sent_at: string | null;
  created_by_name: string | null; sent_by_name: string | null;
};

const STATUS: Record<EmailRow['status'], { label: string; color: 'default' | 'info' | 'success' | 'error' | 'warning' }> = {
  DRAFT: { label: 'Bản nháp', color: 'warning' },
  RECORDED: { label: 'Đã ghi nhận (chưa gửi thật)', color: 'info' },
  SENT: { label: 'Đã gửi', color: 'success' },
  FAILED: { label: 'Gửi lỗi', color: 'error' },
  CANCELLED: { label: 'Đã hủy', color: 'default' },
};

export type EmailRequest = { applicationId: string; template: EmailTemplateCode; trigger: 'MANUAL' | 'STATUS_CHANGE'; nonce: number } | null;

export default function CandidateEmailPanel({ applicationId, request }: { applicationId: string; request?: EmailRequest }) {
  const { t, dateLocale } = useI18n();
  const [emails, setEmails] = useState<EmailRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [openEmail, setOpenEmail] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ template: EmailTemplateCode; trigger: 'MANUAL' | 'STATUS_CHANGE'; draft: EmailDraft | null } | null>(null);

  const load = useCallback(async () => {
    try { setError(null); setEmails((await candidateEmailsApi.forApplication(applicationId)).data.emails); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải thư đã gửi.')); }
    finally { setLoading(false); }
  }, [applicationId, t]);
  useEffect(() => { load(); }, [load]);

  // The page asks for a letter after a status change (interview invite, rejection).
  useEffect(() => {
    // Only for this candidate: the page keeps the request while HR moves to the next one.
    if (!request || request.applicationId !== applicationId) return;
    setExpanded(true);
    setDialog({ template: request.template, trigger: request.trigger, draft: null });
  }, [request, applicationId]);

  const cancel = async (emailId: string) => {
    if (!window.confirm(t('Hủy bản nháp này?'))) return;
    try { await candidateEmailsApi.cancelDraft(emailId); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể hủy bản nháp.')); }
  };

  const templateLabel = (code: string | null) => t(COMPOSE_TEMPLATES.find(item => item.code === code)?.label || 'Thư tự soạn');
  const visible = emails.filter(email => email.status !== 'CANCELLED');

  return (
    <Accordion expanded={expanded} onChange={(_, value) => setExpanded(value)} disableGutters elevation={0}
      sx={{ mb: 3, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography fontWeight={600}>{t('Thư gửi ứng viên ')}{visible.length > 0 ? `(${visible.length})` : ''}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
          <Button variant="contained" color="secondary" size="small" startIcon={<MailOutlineIcon />}
            onClick={() => setDialog({ template: 'ACK_RECEIVED', trigger: 'MANUAL', draft: null })}>
            {t('Soạn thư')}
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
            {t('Hệ thống không tự gửi thư. HR xem lại và bấm gửi cho từng thư.')}
          </Typography>
        </Stack>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
        {loading ? <CircularProgress size={20} /> : emails.length === 0 ? (
          <Typography variant="body2" color="text.secondary">{t('Chưa có thư nào cho ứng viên này.')}</Typography>
        ) : emails.map(email => (
          <Box key={email.email_id} sx={{ py: 1.25, borderTop: '1px solid #EEF2F7', opacity: email.status === 'CANCELLED' ? 0.6 : 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip size="small" label={t(STATUS[email.status].label)} color={STATUS[email.status].color} variant="outlined" />
              <Typography variant="body2" fontWeight={600}>{templateLabel(email.template_code)}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t('tới')} {email.to_address} · {new Date(email.sent_at || email.created_at).toLocaleString(dateLocale)}
                {email.sent_by_name || email.created_by_name ? ` · ${email.sent_by_name || email.created_by_name}` : ''}
              </Typography>
              <Box sx={{ flexGrow: 1 }} />
              <Button size="small" onClick={() => setOpenEmail(openEmail === email.email_id ? null : email.email_id)}>
                {openEmail === email.email_id ? t('Thu gọn') : t('Xem thư')}
              </Button>
              {email.status === 'DRAFT' && <>
                <Button size="small" variant="outlined"
                  onClick={() => setDialog({ template: (email.template_code || 'ACK_RECEIVED') as EmailTemplateCode, trigger: 'MANUAL', draft: email })}>
                  {t('Mở bản nháp')}
                </Button>
                <Button size="small" color="error" onClick={() => cancel(email.email_id)}>{t('Hủy nháp')}</Button>
              </>}
            </Stack>
            <Collapse in={openEmail === email.email_id} unmountOnExit>
              <Box sx={{ mt: 1, p: 1.5, bgcolor: '#F8FAFC', borderRadius: 1, border: '1px solid #E5EAF0' }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {t('Gửi từ')}: {email.from_address}{email.reply_to_address ? ` · ${t('Trả lời về')}: ${email.reply_to_address}` : ''}
                </Typography>
                <Typography variant="body2" fontWeight={600} sx={{ mt: 0.5 }}>{email.subject}</Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 1 }}>{email.body}</Typography>
              </Box>
            </Collapse>
          </Box>
        ))}
      </AccordionDetails>
      <CandidateEmailDialog
        open={!!dialog}
        applicationId={applicationId}
        templateCode={dialog?.template}
        triggerSource={dialog?.trigger}
        draft={dialog?.draft}
        onClose={() => setDialog(null)}
        onDone={() => { setDialog(null); load(); }}
      />
    </Accordion>
  );
}
