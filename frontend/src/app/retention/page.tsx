'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useCallback, useEffect, useState } from 'react';
import { retentionApi } from '@/lib/api';

type CaseStatus = 'PENDING' | 'SCHEDULED_FOR_DELETION' | 'ON_HOLD' | 'DELETED' | 'CANCELLED';
type HoldReason = 'COMPLAINT' | 'INSPECTION' | 'LEGAL_REQUEST' | 'OTHER_LEGAL_BASIS';

interface RetentionHold {
  hold_id: string;
  reason_code: HoldReason;
  legal_approval_reference: string;
  hold_until?: string | null;
  is_expired: boolean;
}

interface RetentionNotification {
  notification_id: string;
  position_title: string;
  position_code: string;
  due_date: string;
  milestone_days: number;
  open_case_count: number;
  days_until_due: number | null;
}

interface RetentionCase {
  retention_case_id: string;
  position_id: string;
  position_title: string;
  position_code: string;
  application_opaque_id?: string | null;
  policy_version: string;
  position_closed_at?: string | null;
  due_date?: string | null;
  status: CaseStatus;
  is_due: boolean;
  confirmed_at?: string | null;
  can_confirm: boolean;
  days_until_due?: number | null;
  cancel_reason?: 'MANUAL' | 'POSITION_REOPENED' | null;
  hold?: RetentionHold | null;
}

interface ClosedPosition { position_id: string; title: string; position_code: string; closed_at?: string | null }

const STATUS_LABELS: Record<CaseStatus, string> = {
  PENDING: 'Chờ xác nhận',
  SCHEDULED_FOR_DELETION: 'Đã xác nhận — chờ xóa',
  ON_HOLD: 'Tạm hoãn xóa',
  DELETED: 'Đã xóa',
  CANCELLED: 'Đã hủy',
};
const STATUS_COLORS: Record<CaseStatus, 'warning' | 'error' | 'default' | 'success' | 'info'> = {
  PENDING: 'warning', SCHEDULED_FOR_DELETION: 'error', ON_HOLD: 'info', DELETED: 'default', CANCELLED: 'success',
};
const HOLD_REASONS: Record<HoldReason, string> = {
  COMPLAINT: 'Đang giải quyết khiếu nại',
  INSPECTION: 'Phục vụ thanh tra, kiểm tra',
  LEGAL_REQUEST: 'Yêu cầu của cơ quan có thẩm quyền',
  OTHER_LEGAL_BASIS: 'Căn cứ pháp lý khác (Pháp chế phê duyệt)',
};
const LEGAL_REFERENCE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 ./_:-]{1,79}$/;

type Action = { kind: 'confirm' | 'cancel' | 'execute' | 'release'; item: RetentionCase };

export default function RetentionPage() {
  const { t, dateLocale } = useI18n();
  const [cases, setCases] = useState<RetentionCase[]>([]);
  const [positions, setPositions] = useState<ClosedPosition[]>([]);
  const [statusFilter, setStatusFilter] = useState<'ALL' | CaseStatus>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [scanPosition, setScanPosition] = useState('');
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<Action | null>(null);
  const [notifications, setNotifications] = useState<RetentionNotification[]>([]);
  const [requiresOtp, setRequiresOtp] = useState(true);
  const [otpChallenge, setOtpChallenge] = useState<{ challenge_id: string; channel: string; dev_code?: string } | null>(null);
  const [otp, setOtp] = useState('');
  const [holdItem, setHoldItem] = useState<RetentionCase | null>(null);
  const [holdReason, setHoldReason] = useState<HoldReason>('COMPLAINT');
  const [holdReference, setHoldReference] = useState('');
  const [holdUntil, setHoldUntil] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await retentionApi.queue(statusFilter === 'ALL' ? undefined : statusFilter);
      setCases(res.data.cases || []);
      setPositions(res.data.closed_positions || []);
      setRequiresOtp(res.data.settings?.purge_requires_otp ?? true);
      setError(null);
      try {
        const notes = await retentionApi.notifications(true);
        setNotifications(notes.data || []);
      } catch { setNotifications([]); }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải danh sách retention"));
    } finally { setLoading(false); }
  }, [statusFilter, t]);

  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    if (!scanPosition || busy) return;
    try {
      setBusy(true); setError(null); setNotice(null);
      const res = await retentionApi.generate(scanPosition);
      setNotice(t("Đã quét vị trí: {0} hồ sơ đến hạn hoặc sắp đến hạn.", res.data.created_count ?? 0));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể quét hồ sơ đến hạn"));
    } finally { setBusy(false); }
  };

  const closeAction = () => { setAction(null); setOtpChallenge(null); setOtp(''); };

  const requestOtp = async () => {
    if (!action || busy) return;
    try {
      setBusy(true); setError(null);
      const res = await retentionApi.requestPurgeOtp(action.item.retention_case_id);
      setOtpChallenge(res.data); setOtp('');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t("Không thể gửi mã OTP"));
      closeAction();
    } finally { setBusy(false); }
  };

  const runAction = async () => {
    if (!action || busy) return;
    const id = action.item.retention_case_id;
    try {
      setBusy(true); setError(null); setNotice(null);
      if (action.kind === 'confirm') await retentionApi.confirm(id);
      else if (action.kind === 'cancel') await retentionApi.cancel(id);
      else if (action.kind === 'release') await retentionApi.releaseHold(id);
      else await retentionApi.execute(id, otpChallenge?.challenge_id, otp.trim());
      setNotice(action.kind === 'confirm' ? t("Đã xác nhận xóa. Hồ sơ chờ thực hiện xóa.")
        : action.kind === 'cancel' ? t("Đã hủy yêu cầu xóa.")
        : action.kind === 'release' ? t("Đã gỡ tạm hoãn. Hồ sơ quay lại chờ xác nhận xóa.")
        : t("Đã xóa dữ liệu ứng viên của hồ sơ này."));
      closeAction();
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t("Thao tác retention không thành công"));
      // A wrong code keeps the dialog open so the user can retry within the limit.
      if (!(action.kind === 'execute' && err.response?.status === 400)) closeAction();
    } finally { setBusy(false); }
  };

  const submitHold = async () => {
    if (!holdItem || busy) return;
    try {
      setBusy(true); setError(null); setNotice(null);
      await retentionApi.hold(holdItem.retention_case_id, {
        reason_code: holdReason, legal_approval_reference: holdReference.trim(), hold_until: holdUntil || null,
      });
      setNotice(t("Đã tạm hoãn xóa hồ sơ theo văn bản Pháp chế."));
      setHoldItem(null); setHoldReference(''); setHoldUntil('');
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : t("Không thể tạm hoãn xóa"));
    } finally { setBusy(false); }
  };

  const markRead = async (id: string) => {
    try { await retentionApi.markNotificationRead(id); } catch { /* the reminder stays visible */ }
    setNotifications(items => items.filter(item => item.notification_id !== id));
  };

  const executeReady = !requiresOtp || (Boolean(otpChallenge) && /^[0-9]{6}$/.test(otp.trim()));

  const fmt = (value?: string | null) => value ? new Date(value).toLocaleDateString(dateLocale) : '—';

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress color="secondary" /></Box>;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Lưu trữ & xóa dữ liệu")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Hồ sơ ứng tuyển đến hạn xem xét retention. Hệ thống không tự xóa: người có quyền phải xác nhận rồi thực hiện xóa, và mọi thao tác đều được ghi audit.")}</Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => load()}>{t("Làm mới")}</Button>
      </Box>

      <Alert severity="info" sx={{ mb: 2 }}>
        {t("Hồ sơ được lưu 12 tháng tính từ ngày đóng vị trí. Hồ sơ có đồng ý lưu để xét các vị trí khác (chưa rút) được lưu đến 5 năm tính từ ngày nhận hồ sơ. Xóa một hồ sơ không ảnh hưởng hồ sơ của cùng ứng viên ở vị trí khác.")}
        {' '}{t("Hồ sơ hiện trong danh sách từ 30 ngày trước hạn; vị trí mở lại sẽ hủy các case cũ và tính lại từ ngày đóng mới.")}
      </Alert>
      {notifications.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>{t("Nhắc hạn retention")}</Typography>
          {notifications.map(note => (
            <Box key={note.notification_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="body2">
                {t("{0} ({1}): {2} hồ sơ đến hạn sau {3} ngày, ngày {4}", note.position_title, note.position_code,
                  note.open_case_count, note.days_until_due ?? note.milestone_days, fmt(note.due_date))}
              </Typography>
              <Button size="small" onClick={() => markRead(note.notification_id)}>{t("Đã xem")}</Button>
            </Box>
          ))}
        </Alert>
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}

      <Card variant="outlined" sx={{ mb: 3 }}><CardContent sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField select size="small" label={t("Vị trí đã đóng")} value={scanPosition} sx={{ minWidth: 320 }}
          onChange={e => setScanPosition(e.target.value)} disabled={positions.length === 0}
          helperText={positions.length === 0 ? t("Không có vị trí đã đóng trong phạm vi của bạn.") : t("Quét để đưa các hồ sơ đã đến hạn vào danh sách chờ xác nhận.")}>
          {positions.map(p => (
            <MenuItem key={p.position_id} value={p.position_id}>{p.title} · {p.position_code} ({t("đóng")} {fmt(p.closed_at)})</MenuItem>
          ))}
        </TextField>
        <Button variant="contained" color="secondary" onClick={scan} disabled={!scanPosition || busy}>{t("Quét hồ sơ đến hạn")}</Button>
      </CardContent></Card>

      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select size="small" label={t("Trạng thái")} value={statusFilter} sx={{ minWidth: 220 }}
          onChange={e => { setLoading(true); setStatusFilter(e.target.value as 'ALL' | CaseStatus); }}>
          <MenuItem value="ALL">{t("Tất cả")}</MenuItem>
          {(Object.keys(STATUS_LABELS) as CaseStatus[]).map(key => <MenuItem key={key} value={key}>{t(STATUS_LABELS[key])}</MenuItem>)}
        </TextField>
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách hồ sơ retention")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Vị trí")}</TableCell>
              <TableCell>{t("Hồ sơ")}</TableCell>
              <TableCell>{t("Ngày đóng")}</TableCell>
              <TableCell>{t("Ngày đến hạn")}</TableCell>
              <TableCell>{t("Còn lại")}</TableCell>
              <TableCell>{t("Trạng thái")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {cases.length === 0 ? (
              <TableRow><TableCell colSpan={7} align="center" sx={{ py: 6, color: 'text.secondary' }}>{t("Không có hồ sơ nào trong danh sách retention")}</TableCell></TableRow>
            ) : cases.map(item => (
              <TableRow key={item.retention_case_id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>{item.position_title}</Typography>
                  <Typography variant="caption" color="text.secondary" fontFamily="monospace">{item.position_code}</Typography>
                </TableCell>
                {/* Only an opaque identifier: candidate PII is never shown in this queue. */}
                <TableCell><Typography variant="caption" fontFamily="monospace">{(item.application_opaque_id || '').slice(0, 12) || '—'}</Typography></TableCell>
                <TableCell>{fmt(item.position_closed_at)}</TableCell>
                <TableCell>
                  {fmt(item.due_date)}
                  {item.is_due && <Chip size="small" color="error" label={t("Đến hạn")} sx={{ ml: 1, height: 20 }} />}
                </TableCell>
                <TableCell>
                  {item.days_until_due === null || item.days_until_due === undefined ? '—'
                    : item.days_until_due <= 0 ? t("Đã đến hạn") : t("{0} ngày", item.days_until_due)}
                </TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLORS[item.status]} label={t(STATUS_LABELS[item.status])} />
                  {item.status === 'CANCELLED' && item.cancel_reason === 'POSITION_REOPENED' && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{t("Vị trí đã mở lại")}</Typography>
                  )}
                  {item.status === 'ON_HOLD' && item.hold && (
                    <Typography variant="caption" color={item.hold.is_expired ? 'error' : 'text.secondary'} sx={{ display: 'block' }}>
                      {t(HOLD_REASONS[item.hold.reason_code])} · {item.hold.legal_approval_reference}
                      {item.hold.hold_until ? ` · ${t("đến")} ${fmt(item.hold.hold_until)}` : ''}
                      {item.hold.is_expired ? ` · ${t("đã quá hạn tạm hoãn")}` : ''}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                  {item.can_confirm && item.status === 'PENDING' && (
                    <Button size="small" color="error" disabled={!item.is_due || busy} onClick={() => setAction({ kind: 'confirm', item })}>{t("Xác nhận xóa")}</Button>
                  )}
                  {item.can_confirm && item.status === 'SCHEDULED_FOR_DELETION' && (
                    <Button size="small" variant="contained" color="error" disabled={busy} onClick={() => setAction({ kind: 'execute', item })}>{t("Thực hiện xóa")}</Button>
                  )}
                  {item.can_confirm && ['PENDING', 'SCHEDULED_FOR_DELETION'].includes(item.status) && (
                    <Button size="small" disabled={busy} onClick={() => setHoldItem(item)}>{t("Tạm hoãn")}</Button>
                  )}
                  {item.can_confirm && item.status === 'ON_HOLD' && (
                    <Button size="small" disabled={busy} onClick={() => setAction({ kind: 'release', item })}>{t("Gỡ tạm hoãn")}</Button>
                  )}
                  {item.can_confirm && ['PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD'].includes(item.status) && (
                    <Button size="small" disabled={busy} onClick={() => setAction({ kind: 'cancel', item })}>{t("Hủy")}</Button>
                  )}
                  {!item.can_confirm && ['PENDING', 'SCHEDULED_FOR_DELETION', 'ON_HOLD'].includes(item.status) && (
                    <Typography variant="caption" color="text.secondary">{t("Cần HR Lead hoặc người được cấp quyền xác nhận")}</Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={!!action} onClose={() => !busy && closeAction()} maxWidth="sm" fullWidth>
        <DialogTitle>
          {action?.kind === 'confirm' ? t("Xác nhận xóa hồ sơ này?") : action?.kind === 'execute' ? t("Thực hiện xóa dữ liệu?")
            : action?.kind === 'release' ? t("Gỡ tạm hoãn xóa?") : t("Hủy yêu cầu xóa?")}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            {action?.kind === 'cancel'
              ? t("Hồ sơ sẽ được giữ lại và rời khỏi danh sách chờ xóa.")
              : action?.kind === 'release'
              ? t("Hồ sơ quay lại trạng thái chờ xác nhận; cần xác nhận xóa lại trước khi thực hiện xóa.")
              : t("Phạm vi xóa (chỉ hồ sơ ứng tuyển này, theo policy {0}): tệp CV gốc và văn bản trích xuất; hồ sơ trích xuất, kết quả đánh giá, xếp hạng và cảnh báo trùng; thông tin định danh, lịch sử trạng thái và ghi chú riêng của HR; mục shortlist, phản hồi và scorecard liên quan. Chỉ còn lại bằng chứng ẩn danh trong nhật ký. Thao tác xóa không hoàn tác được.", action?.item.policy_version || '')}
          </Typography>
          {action && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{action.item.position_title} · {action.item.position_code}</Typography>}
          {action?.kind === 'execute' && requiresOtp && (
            <Box sx={{ mt: 2 }}>
              {!otpChallenge ? (
                <Button variant="outlined" onClick={requestOtp} disabled={busy}>{t("Gửi mã OTP xác nhận")}</Button>
              ) : (
                <>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    {otpChallenge.channel === 'EMAIL' ? t("Đã gửi mã 6 số tới email của bạn. Mã dùng một lần.") : t("Môi trường phát triển: mã OTP hiển thị trực tiếp.")}
                  </Typography>
                  {otpChallenge.dev_code && <Alert severity="warning" sx={{ mb: 1 }}>{t("Mã thử nghiệm: {0}", otpChallenge.dev_code)}</Alert>}
                  <TextField size="small" label={t("Mã OTP")} value={otp} onChange={e => setOtp(e.target.value)}
                    inputProps={{ inputMode: 'numeric', maxLength: 6 }} autoFocus />
                  <Button size="small" sx={{ ml: 1, mt: 0.5 }} onClick={requestOtp} disabled={busy}>{t("Gửi lại mã")}</Button>
                </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeAction} disabled={busy}>{t("Quay lại")}</Button>
          <Button variant="contained" color={action?.kind === 'cancel' || action?.kind === 'release' ? 'primary' : 'error'} onClick={runAction}
            disabled={busy || (action?.kind === 'execute' && !executeReady)}>
            {busy ? t("Đang xử lý…") : t("Đồng ý")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!holdItem} onClose={() => !busy && setHoldItem(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("Tạm hoãn xóa có lý do chính đáng")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {t("Chỉ dùng khi có văn bản phê duyệt của Pháp chế. Không nhập tên hay thông tin của ứng viên; chỉ nhập số/mã văn bản.")}
          </Typography>
          <TextField select fullWidth size="small" label={t("Lý do")} value={holdReason} sx={{ mb: 2 }}
            onChange={e => setHoldReason(e.target.value as HoldReason)}>
            {(Object.keys(HOLD_REASONS) as HoldReason[]).map(key => <MenuItem key={key} value={key}>{t(HOLD_REASONS[key])}</MenuItem>)}
          </TextField>
          <TextField fullWidth size="small" label={t("Số/mã văn bản phê duyệt của Pháp chế")} value={holdReference} sx={{ mb: 2 }}
            onChange={e => setHoldReference(e.target.value)} placeholder="PC-2026/015"
            error={holdReference.length > 0 && !LEGAL_REFERENCE_PATTERN.test(holdReference.trim())}
            helperText={t("Chữ, số và các ký tự . / _ : - (tối đa 80 ký tự)")} />
          <TextField fullWidth size="small" type="date" label={t("Tạm hoãn đến (không bắt buộc)")} value={holdUntil}
            onChange={e => setHoldUntil(e.target.value)} InputLabelProps={{ shrink: true }} />
          {holdItem && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>{holdItem.position_title} · {holdItem.position_code}</Typography>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHoldItem(null)} disabled={busy}>{t("Quay lại")}</Button>
          <Button variant="contained" onClick={submitHold} disabled={busy || !LEGAL_REFERENCE_PATTERN.test(holdReference.trim())}>
            {busy ? t("Đang xử lý…") : t("Tạm hoãn")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
