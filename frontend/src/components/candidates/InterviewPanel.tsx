'use client';

// Interview Coordination panel on a candidate profile:
// 1. Evidence-grounded AI Interview Prep Brief (what to probe + verified strengths)
// 2. Scheduled interview rounds with panelist conflict check, 1-click .ics download,
//    and 1-click bridge to F3.05 INTERVIEW_INVITE (prefills time & place).
import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress,
  Dialog, DialogActions, DialogContent, DialogTitle, Grid, MenuItem, Stack, TextField, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import EventAvailableOutlinedIcon from '@mui/icons-material/EventAvailableOutlined';
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined';
import MailOutlineIcon from '@mui/icons-material/MailOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { interviewsApi, type InterviewFormat, type InterviewStatus } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type Panelist = { user_id: string; display_name: string; email: string | null; panel_role: 'LEAD_INTERVIEWER' | 'INTERVIEWER' | 'OBSERVER' };
type Session = {
  session_id: string; round_no: number; title: string; session_status: InterviewStatus;
  starts_at: string; ends_at: string; slot_vn: string; format: InterviewFormat;
  location_or_link: string | null; prep_notes: string | null; panelists: Panelist[]; can_manage: boolean;
};
type ProbePoint = {
  criterion_id: string; criterion_name: string; category: string; outcome: string;
  priority: 'HIGH' | 'MEDIUM'; suggested_question: string; evidence_quote: string | null; page_number: number | null;
};
type StrengthPoint = { criterion_id: string; criterion_name: string; outcome: string; evidence_quote: string | null };
type PrepBrief = { probe_points: ProbePoint[]; strengths: StrengthPoint[]; probe_count: number; strength_count: number };
type PanelOption = { user_id: string; display_name: string; email: string | null };
type Conflict = { display_name: string; position_code: string | null; round_no: number; slot_vn: string };

const STATUS_META: Record<InterviewStatus, { label: string; color: 'info' | 'success' | 'default' | 'warning' }> = {
  SCHEDULED: { label: 'Đã hẹn', color: 'info' },
  COMPLETED: { label: 'Đã hoàn thành', color: 'success' },
  CANCELLED: { label: 'Đã hủy', color: 'default' },
  NO_SHOW: { label: 'Không tham dự', color: 'warning' },
};

const FORMAT_LABELS: Record<InterviewFormat, string> = {
  ONLINE: 'Trực tuyến',
  ONSITE: 'Trực tiếp',
  PHONE: 'Điện thoại',
};

function defaultDateInput(): string {
  const d = new Date(Date.now() + 86400 * 1000);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function InterviewPanel({
  applicationId,
  onInviteEmail,
}: {
  applicationId: string;
  onInviteEmail?: (slotVn: string, place: string) => void;
}) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [brief, setBrief] = useState<PrepBrief | null>(null);
  const [panelOptions, setPanelOptions] = useState<PanelOption[]>([]);
  const [expanded, setExpanded] = useState(false);

  // Schedule dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [roundNo, setRoundNo] = useState(1);
  const [title, setTitle] = useState('Phỏng vấn chuyên môn');
  const [dateStr, setDateStr] = useState(defaultDateInput);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('10:00');
  const [format, setFormat] = useState<InterviewFormat>('ONLINE');
  const [locationOrLink, setLocationOrLink] = useState('');
  const [prepNotes, setPrepNotes] = useState('');
  const [selectedPanelists, setSelectedPanelists] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);

  const load = useCallback(async () => {
    try {
      setError(null);
      const res = await interviewsApi.forApplication(applicationId);
      setCanManage(Boolean(res.data.can_manage));
      setSessions(res.data.sessions || []);
      setBrief(res.data.prep_brief || null);
      setPanelOptions(res.data.panel_options || []);
      if ((res.data.sessions || []).length > 0) setExpanded(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể tải lịch phỏng vấn.'));
    } finally {
      setLoading(false);
    }
  }, [applicationId, t]);

  useEffect(() => { load(); }, [load]);

  const openScheduleDialog = () => {
    const activeRounds = sessions.filter(s => s.session_status === 'SCHEDULED' || s.session_status === 'COMPLETED').map(s => s.round_no);
    const nextRound = Math.min(10, (activeRounds.length ? Math.max(...activeRounds) : 0) + 1);
    setRoundNo(nextRound);
    setTitle(nextRound === 1 ? 'Phỏng vấn chuyên môn' : `Phỏng vấn vòng ${nextRound}`);
    setDateStr(defaultDateInput());
    setStartTime('09:00');
    setEndTime('10:00');
    setFormat('ONLINE');
    setLocationOrLink('');
    setPrepNotes('');
    setSelectedPanelists([]);
    setFormError(null);
    setConflicts([]);
    setDialogOpen(true);
  };

  const submitSchedule = async (allowConflict = false) => {
    if (busy) return;
    setBusy(true);
    setFormError(null);
    try {
      const startsAt = `${dateStr}T${startTime}:00+07:00`;
      const endsAt = `${dateStr}T${endTime}:00+07:00`;
      await interviewsApi.schedule(applicationId, {
        round_no: roundNo,
        title: title.trim() || 'Phỏng vấn chuyên môn',
        starts_at: startsAt,
        ends_at: endsAt,
        format,
        location_or_link: locationOrLink.trim() || null,
        prep_notes: prepNotes.trim() || null,
        panelists: selectedPanelists.map((uid, idx) => ({
          user_id: uid,
          panel_role: idx === 0 ? 'LEAD_INTERVIEWER' : 'INTERVIEWER',
        })),
        allow_conflict: allowConflict,
      });
      setDialogOpen(false);
      setConflicts([]);
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail && typeof detail === 'object' && Array.isArray(detail.conflicts)) {
        setConflicts(detail.conflicts);
        setFormError(detail.message || t('Có thành viên hội đồng bị trùng lịch phỏng vấn khác.'));
      } else {
        setFormError(typeof detail === 'string' ? detail : t('Không thể đặt lịch phỏng vấn.'));
      }
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (sessionId: string, nextStatus: InterviewStatus) => {
    try {
      setError(null);
      await interviewsApi.update(sessionId, { session_status: nextStatus });
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không thể cập nhật trạng thái buổi phỏng vấn.'));
    }
  };

  const downloadIcs = async (session: Session) => {
    try {
      const res = await interviewsApi.downloadIcs(session.session_id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interview-round-${session.round_no}.ics`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch {
      setError(t('Không thể tải file lịch .ics.'));
    }
  };

  const activeCount = sessions.filter(s => s.session_status !== 'CANCELLED').length;

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, value) => setExpanded(value)}
      disableGutters
      elevation={0}
      sx={{ mb: 3, border: '1px solid', borderColor: 'divider', borderRadius: '10px !important', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1.25} alignItems="center" flexWrap="wrap" useFlexGap>
          <EventAvailableOutlinedIcon fontSize="small" color="primary" />
          <Typography fontWeight={600}>
            {t('Lịch phỏng vấn & gợi ý câu hỏi')} {activeCount > 0 ? `(${activeCount})` : ''}
          </Typography>
          {brief && brief.probe_count > 0 && (
            <Chip size="small" variant="outlined" color="warning" label={t('{0} điểm cần hỏi sâu', brief.probe_count)} />
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{t(error)}</Alert>}
        {loading ? (
          <CircularProgress size={22} />
        ) : (
          <Stack spacing={2.5}>
            {/* Evidence-grounded AI Interview Prep Brief */}
            {brief && (brief.probe_points.length > 0 || brief.strengths.length > 0) && (
              <Box sx={{ p: 2, borderRadius: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider' }}>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.25 }}>
                  <HelpOutlineIcon fontSize="small" color="warning" />
                  <Typography variant="subtitle2" fontWeight={700}>
                    {t('Gợi ý trọng tâm buổi phỏng vấn (từ bằng chứng CV)')}
                  </Typography>
                </Stack>
                {brief.probe_points.length > 0 && (
                  <Stack spacing={1} sx={{ mb: brief.strengths.length > 0 ? 1.75 : 0 }}>
                    {brief.probe_points.slice(0, 5).map(point => (
                      <Box key={point.criterion_id} sx={{ pl: 1.5, borderLeft: '3px solid', borderColor: point.priority === 'HIGH' ? 'warning.main' : 'divider' }}>
                        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                          <Typography variant="body2" fontWeight={600}>{point.criterion_name}</Typography>
                          {point.priority === 'HIGH' && <Chip size="small" color="warning" variant="outlined" label={t('Ưu tiên hỏi')} />}
                        </Stack>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }}>
                          {point.suggested_question}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                )}
                {brief.strengths.length > 0 && (
                  <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                    <CheckCircleOutlineIcon fontSize="small" color="success" />
                    <Typography variant="caption" color="text.secondary" fontWeight={600}>{t('Đã rõ trong CV:')}</Typography>
                    {brief.strengths.map(s => (
                      <Chip key={s.criterion_id} size="small" color="success" variant="outlined" label={s.criterion_name} />
                    ))}
                  </Stack>
                )}
              </Box>
            )}

            {/* Action bar */}
            {canManage && (
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Button variant="contained" color="secondary" size="small" startIcon={<EventAvailableOutlinedIcon />} onClick={openScheduleDialog}>
                  {t('Đặt lịch phỏng vấn')}
                </Button>
                <Typography variant="caption" color="text.secondary">
                  {t('Kiểm tra trùng lịch hội đồng tự động, xuất file .ics và điền sẵn vào thư mời phỏng vấn.')}
                </Typography>
              </Stack>
            )}

            {/* Scheduled sessions */}
            {sessions.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {t('Chưa có buổi phỏng vấn nào được đặt cho ứng viên này.')}
              </Typography>
            ) : (
              <Stack spacing={1.5}>
                {sessions.map(session => (
                  <Box
                    key={session.session_id}
                    sx={{
                      p: 1.75,
                      borderRadius: 2,
                      border: '1px solid',
                      borderColor: 'divider',
                      opacity: session.session_status === 'CANCELLED' ? 0.65 : 1,
                    }}
                  >
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ sm: 'center' }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Chip size="small" color="primary" label={t('Vòng {0}', session.round_no)} />
                        <Typography variant="body2" fontWeight={700}>{session.title}</Typography>
                        <Chip size="small" variant="outlined" color={STATUS_META[session.session_status].color} label={t(STATUS_META[session.session_status].label)} />
                        <Chip size="small" variant="outlined" label={t(FORMAT_LABELS[session.format])} />
                      </Stack>
                      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Button size="small" variant="outlined" startIcon={<CalendarMonthOutlinedIcon />} onClick={() => downloadIcs(session)}>
                          {t('Tải .ics')}
                        </Button>
                        {canManage && onInviteEmail && session.session_status === 'SCHEDULED' && (
                          <Button
                            size="small"
                            variant="contained"
                            color="secondary"
                            startIcon={<MailOutlineIcon />}
                            onClick={() => onInviteEmail(session.slot_vn, session.location_or_link || t(FORMAT_LABELS[session.format]))}
                          >
                            {t('Gửi thư mời PV')}
                          </Button>
                        )}
                        {canManage && session.session_status === 'SCHEDULED' && (
                          <TextField
                            select
                            size="small"
                            value=""
                            SelectProps={{ displayEmpty: true }}
                            sx={{ minWidth: 130 }}
                            onChange={e => { if (e.target.value) changeStatus(session.session_id, e.target.value as InterviewStatus); }}
                          >
                            <MenuItem value="" disabled>{t('Cập nhật')}</MenuItem>
                            <MenuItem value="COMPLETED">{t('Đã hoàn thành')}</MenuItem>
                            <MenuItem value="NO_SHOW">{t('Không tham dự')}</MenuItem>
                            <MenuItem value="CANCELLED">{t('Hủy buổi')}</MenuItem>
                          </TextField>
                        )}
                      </Stack>
                    </Stack>
                    <Typography variant="body2" sx={{ mt: 1, fontWeight: 500 }}>{session.slot_vn}</Typography>
                    {session.location_or_link && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25, wordBreak: 'break-all' }}>
                        {t('Địa điểm / đường dẫn')}: {session.location_or_link}
                      </Typography>
                    )}
                    {session.panelists.length > 0 && (
                      <Stack direction="row" spacing={0.75} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
                        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>{t('Hội đồng:')}</Typography>
                        {session.panelists.map(p => (
                          <Chip key={p.user_id} size="small" variant="outlined" label={p.display_name} />
                        ))}
                      </Stack>
                    )}
                  </Box>
                ))}
              </Stack>
            )}
          </Stack>
        )}
      </AccordionDetails>

      <Dialog open={dialogOpen} onClose={() => !busy && setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700, color: 'primary.main' }}>{t('Đặt lịch phỏng vấn')}</DialogTitle>
        <DialogContent dividers>
          {formError && <Alert severity={conflicts.length > 0 ? 'warning' : 'error'} sx={{ mb: 2 }}>{t(formError)}</Alert>}
          {conflicts.length > 0 && (
            <Box sx={{ mb: 2, p: 1.5, borderRadius: 1.5, bgcolor: 'background.default', border: '1px solid', borderColor: 'warning.light' }}>
              <Typography variant="caption" fontWeight={700} color="warning.main" sx={{ display: 'block', mb: 0.5 }}>
                {t('Lịch bị trùng của thành viên hội đồng:')}
              </Typography>
              {conflicts.map((c, i) => (
                <Typography key={`${c.display_name}-${i}`} variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  • {c.display_name}: {c.position_code || 'HRA'} ({t('Vòng {0}', c.round_no)}) · {c.slot_vn}
                </Typography>
              ))}
            </Box>
          )}
          <Grid container spacing={2} sx={{ pt: 0.5 }}>
            <Grid item xs={4}>
              <TextField
                fullWidth
                size="small"
                type="number"
                label={t('Vòng')}
                value={roundNo}
                inputProps={{ min: 1, max: 10 }}
                onChange={e => setRoundNo(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
              />
            </Grid>
            <Grid item xs={8}>
              <TextField fullWidth size="small" label={t('Tên buổi phỏng vấn')} value={title} onChange={e => setTitle(e.target.value)} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField fullWidth size="small" type="date" label={t('Ngày')} value={dateStr} InputLabelProps={{ shrink: true }}
                onChange={e => setDateStr(e.target.value)} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField fullWidth size="small" type="time" label={t('Bắt đầu (GMT+7)')} value={startTime} InputLabelProps={{ shrink: true }}
                onChange={e => setStartTime(e.target.value)} />
            </Grid>
            <Grid item xs={6} sm={4}>
              <TextField fullWidth size="small" type="time" label={t('Kết thúc (GMT+7)')} value={endTime} InputLabelProps={{ shrink: true }}
                onChange={e => setEndTime(e.target.value)} />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField select fullWidth size="small" label={t('Hình thức')} value={format}
                onChange={e => setFormat(e.target.value as InterviewFormat)}>
                <MenuItem value="ONLINE">{t('Trực tuyến')}</MenuItem>
                <MenuItem value="ONSITE">{t('Trực tiếp')}</MenuItem>
                <MenuItem value="PHONE">{t('Điện thoại')}</MenuItem>
              </TextField>
            </Grid>
            <Grid item xs={12} sm={8}>
              <TextField
                fullWidth
                size="small"
                required={format !== 'ONSITE'}
                label={format === 'ONLINE' ? t('Đường dẫn họp (Teams / Meet)') : format === 'PHONE' ? t('Số điện thoại liên hệ') : t('Phòng họp (tùy chọn)')}
                value={locationOrLink}
                onChange={e => setLocationOrLink(e.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                select
                fullWidth
                size="small"
                label={t('Hội đồng phỏng vấn')}
                SelectProps={{
                  multiple: true,
                  value: selectedPanelists,
                  onChange: e => setSelectedPanelists(typeof e.target.value === 'string' ? e.target.value.split(',') : (e.target.value as string[])),
                  renderValue: selected => {
                    const ids = selected as string[];
                    return ids.map(id => panelOptions.find(o => o.user_id === id)?.display_name || id).join(', ');
                  },
                }}
              >
                {panelOptions.map(opt => (
                  <MenuItem key={opt.user_id} value={opt.user_id}>{opt.display_name}{opt.email ? ` (${opt.email})` : ''}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField fullWidth size="small" multiline minRows={2} label={t('Ghi chú chuẩn bị (tùy chọn)')}
                value={prepNotes} onChange={e => setPrepNotes(e.target.value)} inputProps={{ maxLength: 2000 }} />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDialogOpen(false)} disabled={busy}>{t('Hủy')}</Button>
          {conflicts.length > 0 ? (
            <Button variant="contained" color="warning" onClick={() => submitSchedule(true)} disabled={busy}>
              {busy ? <CircularProgress size={18} color="inherit" /> : t('Vẫn đặt lịch')}
            </Button>
          ) : (
            <Button variant="contained" color="secondary" onClick={() => submitSchedule(false)}
              disabled={busy || !dateStr || !startTime || !endTime || (format !== 'ONSITE' && !locationOrLink.trim())}>
              {busy ? <CircularProgress size={18} color="inherit" /> : t('Lưu lịch phỏng vấn')}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Accordion>
  );
}
