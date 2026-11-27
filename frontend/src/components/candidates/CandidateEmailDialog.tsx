'use client';

// F3.05: HR reviews a prefilled letter (sender, recipient, subject, body), edits it and
// sends it. Nothing goes out on its own; in "record" mode sending only stores it.
import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Grid, MenuItem,
  TextField, Typography,
} from '@mui/material';
import { candidateEmailsApi, type EmailTemplateCode } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

// POOL_INVITE is not offered here: it is only written from a Talent Pool scan (see poolScanId).
export const COMPOSE_TEMPLATES: { code: EmailTemplateCode; label: string }[] = [
  { code: 'ACK_RECEIVED', label: 'Xác nhận đã nhận hồ sơ' },
  { code: 'REQUEST_INFO', label: 'Mời bổ sung thông tin' },
  { code: 'INTERVIEW_INVITE', label: 'Mời phỏng vấn' },
  { code: 'REJECTION', label: 'Thông báo chưa phù hợp' },
];

export const TEMPLATE_LABELS: Record<string, string> = {
  ...Object.fromEntries(COMPOSE_TEMPLATES.map(item => [item.code, item.label])),
  POOL_INVITE: 'Mời trao đổi (Talent Pool)',
};

const PLACEHOLDER = /\{(ho_ten|vi_tri|ma_vi_tri|ngay_nop|ten_hr|email_hr|thoi_gian_pv|dia_diem_pv)\}/g;
const EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

export type EmailDraft = {
  email_id: string; template_code: EmailTemplateCode | null; to_address: string; subject: string; body: string;
  from_address: string; reply_to_address: string | null;
};

type Props = {
  open: boolean;
  applicationId: string;
  templateCode?: EmailTemplateCode;
  /** Talent Pool invitation: the scan whose CONTACT decision and contact reveal allow it. */
  poolScanId?: string;
  /** Optional prefill from a scheduled interview session (fills {thoi_gian_pv} and {dia_diem_pv}). */
  prefillInterview?: { time?: string; place?: string } | null;
  triggerSource?: 'MANUAL' | 'STATUS_CHANGE';
  draft?: EmailDraft | null;
  onClose: () => void;
  onDone: () => void;
};

export function unresolvedPlaceholders(...parts: string[]): string[] {
  const found = new Set<string>();
  parts.forEach(part => { for (const m of (part || '').matchAll(PLACEHOLDER)) found.add(m[1]); });
  return Array.from(found).sort();
}

export default function CandidateEmailDialog({ open, applicationId, templateCode = 'ACK_RECEIVED', poolScanId, prefillInterview, triggerSource = 'MANUAL', draft, onClose, onDone }: Props) {
  const { t } = useI18n();
  const [template, setTemplate] = useState<EmailTemplateCode>(templateCode);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sender, setSender] = useState<{ from_address: string; reply_to_address: string | null; send_mode: string } | null>(null);
  const [toAddress, setToAddress] = useState('');
  const [toSource, setToSource] = useState<'PROFILE' | 'NONE' | 'DRAFT'>('PROFILE');
  const [profileEmail, setProfileEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [interviewTime, setInterviewTime] = useState('');
  const [interviewPlace, setInterviewPlace] = useState('');
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmPool, setConfirmPool] = useState(false);

  // Load a fresh prefilled letter (or the saved draft) each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    let active = true;
    setError(null); setConfirmReject(false); setConfirmPool(false); setInterviewTime(''); setInterviewPlace('');
    setLoading(true);
    const load = draft
      ? candidateEmailsApi.forApplication(applicationId).then(res => {
          if (!active) return;
          setSender({ from_address: draft.from_address, reply_to_address: draft.reply_to_address, send_mode: res.data.send_mode });
          setTemplate(draft.template_code || 'ACK_RECEIVED');
          setToAddress(draft.to_address); setToSource('DRAFT'); setProfileEmail(res.data.candidate_email || '');
          setSubject(draft.subject); setBody(draft.body); setWarnings([]);
        })
      : candidateEmailsApi.compose(applicationId, template, poolScanId).then(res => {
          if (!active) return;
          const d = res.data;
          setSender({ from_address: d.from_address, reply_to_address: d.reply_to_address, send_mode: d.send_mode });
          setToAddress(d.to_address); setToSource(d.to_source); setProfileEmail(d.to_address);
          const preTime = (prefillInterview?.time || '').trim();
          const prePlace = (prefillInterview?.place || '').trim();
          const fill = (value: string) => {
            let out = value;
            if (preTime) out = out.split('{thoi_gian_pv}').join(preTime);
            if (prePlace) out = out.split('{dia_diem_pv}').join(prePlace);
            return out;
          };
          setSubject(fill(d.subject)); setBody(fill(d.body)); setWarnings(d.warnings || []);
          if (preTime) setInterviewTime(preTime);
          if (prePlace) setInterviewPlace(prePlace);
        });
    load.catch((err: any) => { if (active) setError(err.response?.data?.detail || t('Không thể soạn thư.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // A template change reloads the letter; the draft and application come with the open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, applicationId, template, draft, poolScanId]);

  useEffect(() => { if (open && !draft) setTemplate(templateCode); }, [open, templateCode, draft]);

  const unresolved = useMemo(() => unresolvedPlaceholders(subject, body), [subject, body]);
  const needsInterview = unresolved.includes('thoi_gian_pv') || unresolved.includes('dia_diem_pv');
  const validTo = EMAIL.test(toAddress.trim());
  const isRejection = template === 'REJECTION';
  const isPoolInvite = template === 'POOL_INVITE';
  const recordOnly = sender?.send_mode !== 'smtp';

  const fillInterview = () => {
    const apply = (value: string) => value
      .split('{thoi_gian_pv}').join(interviewTime.trim() || '{thoi_gian_pv}')
      .split('{dia_diem_pv}').join(interviewPlace.trim() || '{dia_diem_pv}');
    setSubject(apply(subject)); setBody(apply(body));
  };

  const save = async (send: boolean) => {
    if (busy) return;
    if (send && isRejection && !confirmReject) { setConfirmReject(true); return; }
    if (send && isPoolInvite && !confirmPool) { setConfirmPool(true); return; }
    try {
      setBusy(true); setError(null);
      const payload = { to_address: toAddress.trim(), subject: subject.trim(), body };
      if (draft) {
        await candidateEmailsApi.updateDraft(draft.email_id, payload);
        if (send) {
          const res = await candidateEmailsApi.sendDraft(draft.email_id, isRejection || isPoolInvite);
          if (res.data.status === 'FAILED') throw { response: { data: { detail: t('Gửi thư không thành công. Thư đã được lưu với trạng thái lỗi.') } } };
        }
      } else {
        const res = await candidateEmailsApi.create(applicationId, {
          ...payload, template_code: template, trigger_source: triggerSource, send, confirmed: isRejection || isPoolInvite,
          ...(poolScanId ? { scan_id: poolScanId } : {}),
        });
        if (send && res.data.status === 'FAILED') throw { response: { data: { detail: t('Gửi thư không thành công. Thư đã được lưu với trạng thái lỗi.') } } };
      }
      onDone();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể lưu thư.'));
      setConfirmReject(false); setConfirmPool(false);
    } finally { setBusy(false); }
  };

  const toHelper = toSource === 'DRAFT' ? t('Địa chỉ đã lưu trong bản nháp.')
    : toSource === 'NONE' ? t('Hồ sơ chưa có email. Vui lòng nhập email của ứng viên.')
    : toAddress.trim() !== profileEmail ? t('Bạn đã sửa địa chỉ; email trong hồ sơ không thay đổi.')
    : t('Lấy từ hồ sơ ứng viên (trích từ CV). Hãy kiểm tra trước khi gửi.');

  return (
    <Dialog open={open} onClose={() => !busy && onClose()} maxWidth="md" fullWidth>
      <DialogTitle sx={{ color: '#0A2B57', fontWeight: 700 }}>{draft ? t('Bản nháp thư gửi ứng viên') : t('Soạn thư gửi ứng viên')}</DialogTitle>
      <DialogContent dividers>
        {loading ? <Box sx={{ py: 6, textAlign: 'center' }}><CircularProgress size={28} /></Box> : (
          <>
            {recordOnly && (
              <Alert severity="info" sx={{ mb: 2 }}>
                {t('Chế độ thử: bấm "Gửi thư" chỉ lưu thư vào lịch sử hồ sơ, hệ thống chưa gửi email thật cho ứng viên.')}
              </Alert>
            )}
            {warnings.includes('ALREADY_SENT') && <Alert severity="warning" sx={{ mb: 2 }}>{t('Ứng viên đã nhận một thư cùng loại trước đó. Hãy kiểm tra để không gửi trùng.')}</Alert>}
            {warnings.includes('DRAFT_EXISTS') && <Alert severity="warning" sx={{ mb: 2 }}>{t('Đã có một bản nháp cùng loại cho hồ sơ này.')}</Alert>}
            {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
            <Grid container spacing={2}>
              {!draft && !poolScanId && (
                <Grid item xs={12}>
                  <TextField select fullWidth size="small" label={t('Mẫu thư')} value={template}
                    onChange={e => setTemplate(e.target.value as EmailTemplateCode)} disabled={busy}>
                    {COMPOSE_TEMPLATES.map(item => <MenuItem key={item.code} value={item.code}>{t(item.label)}</MenuItem>)}
                  </TextField>
                </Grid>
              )}
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('Gửi từ')} value={sender?.from_address || ''} InputProps={{ readOnly: true }}
                  helperText={t('Địa chỉ HR dùng để gửi thư. Admin cấu hình hộp thư tuyển dụng chung.')} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField fullWidth size="small" label={t('Ứng viên trả lời về')} value={sender?.reply_to_address || ''} InputProps={{ readOnly: true }}
                  helperText={t('Email tài khoản HR của bạn.')} />
              </Grid>
              <Grid item xs={12}>
                <TextField fullWidth size="small" required label={t('Gửi tới (email ứng viên)')} value={toAddress}
                  onChange={e => setToAddress(e.target.value)} disabled={busy} inputProps={{ maxLength: 320 }}
                  error={!!toAddress && !validTo} helperText={toAddress && !validTo ? t('Địa chỉ email không hợp lệ.') : toHelper} />
              </Grid>
              {needsInterview && (
                <Grid item xs={12}>
                  <Box sx={{ p: 1.5, border: '1px dashed #C9D3E0', borderRadius: 2, bgcolor: '#F8FAFC' }}>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>{t('Thông tin buổi phỏng vấn')}</Typography>
                    <Grid container spacing={1.5} alignItems="center">
                      <Grid item xs={12} sm={5}>
                        <TextField fullWidth size="small" label={t('Thời gian')} placeholder="09:00, 25/11/2026"
                          value={interviewTime} onChange={e => setInterviewTime(e.target.value)} disabled={busy} />
                      </Grid>
                      <Grid item xs={12} sm={5}>
                        <TextField fullWidth size="small" label={t('Địa điểm hoặc đường dẫn')} placeholder="Phòng I-201 / Teams link"
                          value={interviewPlace} onChange={e => setInterviewPlace(e.target.value)} disabled={busy} />
                      </Grid>
                      <Grid item xs={12} sm={2}>
                        <Button fullWidth variant="outlined" onClick={fillInterview} disabled={busy || (!interviewTime.trim() && !interviewPlace.trim())}>
                          {t('Điền vào thư')}
                        </Button>
                      </Grid>
                    </Grid>
                  </Box>
                </Grid>
              )}
              <Grid item xs={12}>
                <TextField fullWidth size="small" required label={t('Tiêu đề')} value={subject}
                  onChange={e => setSubject(e.target.value)} disabled={busy} inputProps={{ maxLength: 300 }} />
              </Grid>
              <Grid item xs={12}>
                <TextField fullWidth multiline minRows={12} required label={t('Nội dung')} value={body}
                  onChange={e => setBody(e.target.value)} disabled={busy} inputProps={{ maxLength: 20000 }} />
              </Grid>
            </Grid>
            {unresolved.length > 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {t('Thư còn chỗ chưa điền:')} {unresolved.map(name => `{${name}}`).join(', ')}
              </Alert>
            )}
            {confirmPool && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {t('Bạn sắp gửi thư mời trao đổi tới')} <strong>{toAddress.trim()}</strong>. {t('Ứng viên đã đồng ý cho VinUni lưu hồ sơ để cân nhắc các vị trí khác (Talent Pool). Mục đích thư: mời trao đổi cơ hội tuyển dụng. Bấm "Xác nhận gửi thư mời" để gửi.')}
              </Alert>
            )}
            {confirmReject && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {t('Đây là thư thông báo chưa phù hợp. Bấm "Xác nhận gửi thư từ chối" để gửi; kiểm tra kỹ người nhận trước khi gửi.')}
              </Alert>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} disabled={busy}>{t('Hủy')}</Button>
        <Button variant="outlined" onClick={() => save(false)} disabled={busy || loading || !subject.trim() || !body.trim() || !toAddress.trim()}>
          {t('Lưu nháp')}
        </Button>
        <Button variant="contained" color={isRejection ? 'error' : 'secondary'} onClick={() => save(true)}
          disabled={busy || loading || !validTo || !subject.trim() || !body.trim() || unresolved.length > 0}>
          {busy ? <CircularProgress size={18} color="inherit" /> : confirmReject ? t('Xác nhận gửi thư từ chối') : confirmPool ? t('Xác nhận gửi thư mời') : t('Gửi thư')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
