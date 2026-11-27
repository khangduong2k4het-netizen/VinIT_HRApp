'use client';

// F3.05 Phase 2 — Human-in-the-Loop Batch Email Review Queue.
// Never sends blindly in bulk: HR picks candidates & a template, then steps through
// each candidate 1 by 1 (1 / N), inspects/edits the real recipient, subject and body,
// ticks explicit confirmation for REJECTION, and sends individually via F3.05 endpoints.
import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  LinearProgress,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import { candidateEmailsApi, type EmailTemplateCode } from '@/lib/api';
import { COMPOSE_TEMPLATES, unresolvedPlaceholders } from '@/components/candidates/CandidateEmailDialog';
import { APPLICATION_STATUSES, isApplicationStatus } from '@/lib/applicationStatus';
import { useI18n } from '@/i18n/I18nProvider';

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const MAX_BATCH_SIZE = 20;

export interface BatchEmailCandidate {
  application_id: string;
  candidate_name: string;
  application_status?: string;
  matching_score?: number | null;
}

type StatusFilter = 'ALL' | 'SHORTLIST' | 'INTERVIEW' | 'REJECTED_SCREENING' | 'NEW';
type OutcomeStatus = 'SENT' | 'SKIPPED' | 'FAILED';

interface BatchOutcome {
  application_id: string;
  candidate_name: string;
  status: OutcomeStatus;
  detail?: string;
}

interface BatchCandidateEmailDialogProps {
  open: boolean;
  candidates: BatchEmailCandidate[];
  initialSelectedIds?: string[];
  onClose: () => void;
  onDone: () => void;
}

export default function BatchCandidateEmailDialog({
  open,
  candidates,
  initialSelectedIds = [],
  onClose,
  onDone,
}: BatchCandidateEmailDialogProps) {
  const { t } = useI18n();
  const [step, setStep] = useState<'select' | 'review' | 'summary'>('select');
  const [template, setTemplate] = useState<EmailTemplateCode>('ACK_RECEIVED');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sharedTime, setSharedTime] = useState('');
  const [sharedPlace, setSharedPlace] = useState('');

  // Step 2 queue state
  const [queue, setQueue] = useState<BatchEmailCandidate[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sender, setSender] = useState<{ from_address: string; reply_to_address: string | null; send_mode: string } | null>(null);
  const [toAddress, setToAddress] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [confirmReject, setConfirmReject] = useState(false);
  const [outcomes, setOutcomes] = useState<BatchOutcome[]>([]);

  useEffect(() => {
    if (!open) return;
    setStep('select');
    setStatusFilter('ALL');
    setSharedTime('');
    setSharedPlace('');
    setQueue([]);
    setCurrentIndex(0);
    setOutcomes([]);
    setError(null);
    const validInitial = initialSelectedIds
      .filter(id => candidates.some(c => c.application_id === id))
      .slice(0, MAX_BATCH_SIZE);
    setSelectedIds(validInitial);
  }, [open, candidates, initialSelectedIds]);

  const filteredCandidates = useMemo(() => {
    if (statusFilter === 'ALL') return candidates;
    return candidates.filter(c => c.application_status === statusFilter);
  }, [candidates, statusFilter]);

  const toggleCandidate = (id: string) => {
    setSelectedIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id);
      if (prev.length >= MAX_BATCH_SIZE) return prev;
      return [...prev, id];
    });
  };

  const selectVisible = () => {
    const next = new Set(selectedIds);
    for (const c of filteredCandidates) {
      if (next.size >= MAX_BATCH_SIZE) break;
      next.add(c.application_id);
    }
    setSelectedIds(Array.from(next));
  };

  const currentCandidate = queue[currentIndex] || null;

  const loadCandidateLetter = useCallback(async (candidate: BatchEmailCandidate) => {
    setLoadingDraft(true);
    setError(null);
    setConfirmReject(false);
    try {
      const res = await candidateEmailsApi.compose(candidate.application_id, template);
      const d = res.data;
      setSender({ from_address: d.from_address, reply_to_address: d.reply_to_address, send_mode: d.send_mode });
      setToAddress(d.to_address || '');
      const preTime = sharedTime.trim();
      const prePlace = sharedPlace.trim();
      const applyShared = (val: string) => {
        let out = val || '';
        if (preTime) out = out.split('{thoi_gian_pv}').join(preTime);
        if (prePlace) out = out.split('{dia_diem_pv}').join(prePlace);
        return out;
      };
      setSubject(applyShared(d.subject));
      setBody(applyShared(d.body));
      setWarnings(d.warnings || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể soạn thư cho ứng viên này.'));
      setToAddress('');
      setSubject('');
      setBody('');
      setWarnings([]);
    } finally {
      setLoadingDraft(false);
    }
  }, [template, sharedTime, sharedPlace, t]);

  useEffect(() => {
    if (step === 'review' && currentCandidate) {
      loadCandidateLetter(currentCandidate);
    }
  }, [step, currentCandidate, loadCandidateLetter]);

  const startReview = () => {
    const picked = candidates.filter(c => selectedIds.includes(c.application_id)).slice(0, MAX_BATCH_SIZE);
    if (picked.length === 0) return;
    setQueue(picked);
    setCurrentIndex(0);
    setOutcomes([]);
    setStep('review');
  };

  const advance = (outcome: BatchOutcome) => {
    const nextOutcomes = [...outcomes, outcome];
    setOutcomes(nextOutcomes);
    if (currentIndex + 1 < queue.length) {
      setCurrentIndex(currentIndex + 1);
    } else {
      setStep('summary');
    }
  };

  const handleSkip = () => {
    if (!currentCandidate || sending) return;
    advance({
      application_id: currentCandidate.application_id,
      candidate_name: currentCandidate.candidate_name,
      status: 'SKIPPED',
    });
  };

  const handleSendCurrent = async () => {
    if (!currentCandidate || sending) return;
    setSending(true);
    setError(null);
    try {
      const res = await candidateEmailsApi.create(currentCandidate.application_id, {
        template_code: template,
        trigger_source: 'MANUAL',
        to_address: toAddress.trim(),
        subject: subject.trim(),
        body,
        send: true,
        confirmed: template === 'REJECTION',
      });
      if (res.data.status === 'FAILED') {
        advance({
          application_id: currentCandidate.application_id,
          candidate_name: currentCandidate.candidate_name,
          status: 'FAILED',
          detail: t('Gửi thư không thành công. Thư đã được lưu với trạng thái lỗi.'),
        });
      } else {
        advance({
          application_id: currentCandidate.application_id,
          candidate_name: currentCandidate.candidate_name,
          status: 'SENT',
        });
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể gửi thư. Bạn có thể sửa lại hoặc bỏ qua ứng viên này.'));
    } finally {
      setSending(false);
    }
  };

  const unresolved = useMemo(() => unresolvedPlaceholders(subject, body), [subject, body]);
  const validTo = EMAIL_RE.test(toAddress.trim());
  const isRejection = template === 'REJECTION';
  const recordOnly = sender?.send_mode !== 'smtp';
  const canSendCurrent = Boolean(
    !loadingDraft &&
    !sending &&
    validTo &&
    subject.trim() &&
    body.trim() &&
    unresolved.length === 0 &&
    (!isRejection || confirmReject)
  );

  const sentCount = outcomes.filter(o => o.status === 'SENT').length;
  const skippedCount = outcomes.filter(o => o.status === 'SKIPPED').length;
  const failedCount = outcomes.filter(o => o.status === 'FAILED').length;

  const filterChips: { value: StatusFilter; label: string }[] = [
    { value: 'ALL', label: t('Tất cả') },
    { value: 'SHORTLIST', label: t('Shortlist') },
    { value: 'INTERVIEW', label: t('Phỏng vấn') },
    { value: 'REJECTED_SCREENING', label: t('Loại vòng sàng lọc') },
    { value: 'NEW', label: t('Mới') },
  ];

  return (
    <Dialog open={open} onClose={() => !sending && onClose()} maxWidth="md" fullWidth>
      <DialogTitle sx={{ color: '#0A2B57', fontWeight: 700 }}>
        {t('Soạn thư hàng loạt (duyệt từng người)')}
      </DialogTitle>

      <DialogContent dividers>
        {step === 'select' && (
          <Stack spacing={2}>
            <Alert severity="info">
              {t('Hệ thống không gửi tự động hàng loạt: bạn sẽ xem lại người nhận, tiêu đề và nội dung của từng ứng viên trước khi gửi.')}
            </Alert>

            <TextField
              select
              fullWidth
              size="small"
              label={t('Mẫu thư áp dụng cho đợt này')}
              value={template}
              onChange={e => setTemplate(e.target.value as EmailTemplateCode)}
            >
              {COMPOSE_TEMPLATES.map(item => (
                <MenuItem key={item.code} value={item.code}>{t(item.label)}</MenuItem>
              ))}
            </TextField>

            {template === 'INTERVIEW_INVITE' && (
              <Box sx={{ p: 1.5, border: '1px dashed #C9D3E0', borderRadius: 2, bgcolor: '#F8FAFC' }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t('Thông tin phỏng vấn dùng chung (tùy chọn — vẫn chỉnh được theo từng người)')}
                </Typography>
                <Grid container spacing={1.5}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      size="small"
                      label={t('Thời gian')}
                      placeholder="09:00, 28/11/2026"
                      value={sharedTime}
                      onChange={e => setSharedTime(e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      size="small"
                      label={t('Địa điểm hoặc đường dẫn')}
                      placeholder="Phòng I-201 / Teams link"
                      value={sharedPlace}
                      onChange={e => setSharedPlace(e.target.value)}
                    />
                  </Grid>
                </Grid>
              </Box>
            )}

            <Box>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  {filterChips.map(chip => (
                    <Chip
                      key={chip.value}
                      size="small"
                      label={chip.label}
                      color={statusFilter === chip.value ? 'primary' : 'default'}
                      variant={statusFilter === chip.value ? 'filled' : 'outlined'}
                      onClick={() => setStatusFilter(chip.value)}
                    />
                  ))}
                </Stack>
                <Stack direction="row" spacing={1}>
                  <Button size="small" onClick={selectVisible} disabled={filteredCandidates.length === 0}>
                    {t('Chọn đang hiện')}
                  </Button>
                  <Button size="small" onClick={() => setSelectedIds([])} disabled={selectedIds.length === 0}>
                    {t('Bỏ chọn')}
                  </Button>
                </Stack>
              </Stack>

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                {t('Đã chọn {0}/{1} ứng viên (tối đa {2} người mỗi đợt rà soát).', selectedIds.length, candidates.length, MAX_BATCH_SIZE)}
              </Typography>

              <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, maxHeight: 280, overflowY: 'auto' }}>
                {filteredCandidates.length === 0 ? (
                  <Box sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('Không có ứng viên nào trong nhóm lọc này.')}
                    </Typography>
                  </Box>
                ) : (
                  <List dense disablePadding>
                    {filteredCandidates.map(c => {
                      const checked = selectedIds.includes(c.application_id);
                      const disabled = !checked && selectedIds.length >= MAX_BATCH_SIZE;
                      const statusMeta = c.application_status && isApplicationStatus(c.application_status)
                        ? t(APPLICATION_STATUSES[c.application_status].label)
                        : c.application_status || '';
                      return (
                        <ListItemButton
                          key={c.application_id}
                          onClick={() => !disabled && toggleCandidate(c.application_id)}
                          disabled={disabled}
                          divider
                        >
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            <Checkbox edge="start" size="small" checked={checked} tabIndex={-1} disableRipple />
                          </ListItemIcon>
                          <ListItemText
                            primary={c.candidate_name}
                            secondary={`${statusMeta}${c.matching_score != null ? ` · ${c.matching_score}%` : ''}`}
                          />
                        </ListItemButton>
                      );
                    })}
                  </List>
                )}
              </Box>
            </Box>
          </Stack>
        )}

        {step === 'review' && currentCandidate && (
          <Stack spacing={2}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
                <Typography variant="subtitle1" fontWeight={700} color="primary.main">
                  {t('Ứng viên {0}/{1}', currentIndex + 1, queue.length)}: {currentCandidate.candidate_name}
                </Typography>
                <Stack direction="row" spacing={0.75}>
                  <Chip size="small" color="success" variant="outlined" label={`${t('Đã gửi')}: ${sentCount}`} />
                  <Chip size="small" variant="outlined" label={`${t('Bỏ qua')}: ${skippedCount}`} />
                  {failedCount > 0 && <Chip size="small" color="error" variant="outlined" label={`${t('Lỗi')}: ${failedCount}`} />}
                </Stack>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.round(((currentIndex + 1) / queue.length) * 100)}
                sx={{ height: 6, borderRadius: 3 }}
              />
            </Box>

            {loadingDraft ? (
              <Box sx={{ py: 6, textAlign: 'center' }}><CircularProgress size={28} /></Box>
            ) : (
              <>
                {recordOnly && (
                  <Alert severity="info">
                    {t('Chế độ thử: bấm "Gửi thư" chỉ lưu thư vào lịch sử hồ sơ, hệ thống chưa gửi email thật cho ứng viên.')}
                  </Alert>
                )}
                {warnings.includes('ALREADY_SENT') && (
                  <Alert severity="warning">
                    {t('Ứng viên đã nhận một thư cùng loại trước đó. Hãy kiểm tra để không gửi trùng.')}
                  </Alert>
                )}
                {warnings.includes('DRAFT_EXISTS') && (
                  <Alert severity="warning">
                    {t('Đã có một bản nháp cùng loại cho hồ sơ này.')}
                  </Alert>
                )}
                {error && <Alert severity="error">{t(error)}</Alert>}

                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      size="small"
                      required
                      label={t('Gửi tới (email ứng viên)')}
                      value={toAddress}
                      onChange={e => setToAddress(e.target.value)}
                      disabled={sending}
                      error={!!toAddress && !validTo}
                      helperText={
                        !toAddress.trim()
                          ? t('Hồ sơ chưa có email. Vui lòng nhập email của ứng viên.')
                          : !validTo
                            ? t('Địa chỉ email không hợp lệ.')
                            : t('Lấy từ hồ sơ ứng viên (trích từ CV). Hãy kiểm tra trước khi gửi.')
                      }
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      size="small"
                      required
                      label={t('Tiêu đề')}
                      value={subject}
                      onChange={e => setSubject(e.target.value)}
                      disabled={sending}
                      inputProps={{ maxLength: 300 }}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      multiline
                      minRows={9}
                      required
                      label={t('Nội dung')}
                      value={body}
                      onChange={e => setBody(e.target.value)}
                      disabled={sending}
                      inputProps={{ maxLength: 20000 }}
                    />
                  </Grid>
                </Grid>

                {unresolved.length > 0 && (
                  <Alert severity="warning">
                    {t('Thư còn chỗ chưa điền:')} {unresolved.map(name => `{${name}}`).join(', ')}
                  </Alert>
                )}

                {isRejection && (
                  <Alert severity="error" icon={false}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={confirmReject}
                          onChange={e => setConfirmReject(e.target.checked)}
                          color="error"
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2">
                          {t('Tôi đã kiểm tra đúng người nhận và xác nhận gửi thư thông báo chưa phù hợp.')}
                        </Typography>
                      }
                    />
                  </Alert>
                )}
              </>
            )}
          </Stack>
        )}

        {step === 'summary' && (
          <Stack spacing={2}>
            <Alert severity={failedCount > 0 ? 'warning' : 'success'}>
              {t('Hoàn tất đợt rà soát thư: {0} đã gửi, {1} bỏ qua, {2} lỗi.', sentCount, skippedCount, failedCount)}
            </Alert>
            <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, maxHeight: 320, overflowY: 'auto' }}>
              <List dense disablePadding>
                {outcomes.map(item => (
                  <ListItemButton key={item.application_id} divider disableRipple sx={{ cursor: 'default' }}>
                    <ListItemIcon sx={{ minWidth: 34 }}>
                      {item.status === 'SENT' ? (
                        <CheckCircleOutlineIcon fontSize="small" color="success" />
                      ) : item.status === 'FAILED' ? (
                        <ErrorOutlineIcon fontSize="small" color="error" />
                      ) : (
                        <SkipNextIcon fontSize="small" color="action" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.candidate_name}
                      secondary={
                        item.status === 'SENT'
                          ? t('Đã gửi')
                          : item.status === 'SKIPPED'
                            ? t('Bỏ qua')
                            : item.detail || t('Lỗi')
                      }
                    />
                  </ListItemButton>
                ))}
              </List>
            </Box>
          </Stack>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        {step === 'select' && (
          <>
            <Button onClick={onClose}>{t('Hủy')}</Button>
            <Button
              variant="contained"
              color="secondary"
              disabled={selectedIds.length === 0}
              onClick={startReview}
            >
              {t('Bắt đầu rà soát ({0})', selectedIds.length)}
            </Button>
          </>
        )}

        {step === 'review' && (
          <>
            <Button onClick={() => setStep('select')} disabled={sending}>
              {t('Quay lại')}
            </Button>
            <Button variant="outlined" onClick={handleSkip} disabled={sending || loadingDraft}>
              {t('Bỏ qua người này')}
            </Button>
            <Button
              variant="contained"
              color={isRejection ? 'error' : 'secondary'}
              disabled={!canSendCurrent}
              onClick={handleSendCurrent}
            >
              {sending ? (
                <CircularProgress size={18} color="inherit" />
              ) : currentIndex + 1 < queue.length ? (
                t('Gửi & sang người tiếp theo')
              ) : (
                t('Gửi & hoàn tất')
              )}
            </Button>
          </>
        )}

        {step === 'summary' && (
          <Button variant="contained" color="secondary" onClick={onDone}>
            {t('Đóng')}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
