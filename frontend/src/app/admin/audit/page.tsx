'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, MenuItem, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TablePagination, TableRow, TextField, Typography,
} from '@mui/material';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import { useCallback, useEffect, useState } from 'react';
import { auditApi } from '@/lib/api';

interface AuditEvent {
  event_id: string;
  created_at: string;
  action_type: string;
  object_type: string;
  object_id?: string | null;
  outcome?: string | null;
  actor_user_id?: string | null;
  actor_name?: string | null;
  position_id?: string | null;
  position_title?: string | null;
  position_code?: string | null;
}

interface Integrity { valid: boolean; checked_events: number; broken_events: number }

export default function AuditLogPage() {
  const { t, dateLocale } = useI18n();
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [actionTypes, setActionTypes] = useState<string[]>([]);
  const [actionType, setActionType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [verifying, setVerifying] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await auditApi.list({
        action_type: actionType || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined,
        page: page + 1, page_size: pageSize,
      });
      setItems(res.data.items || []); setTotal(res.data.total || 0); setActionTypes(res.data.action_types || []);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải nhật ký audit"));
    } finally { setLoading(false); }
  }, [actionType, dateFrom, dateTo, page, pageSize, t]);

  useEffect(() => { load(); }, [load]);

  const verify = async () => {
    try {
      setVerifying(true);
      setIntegrity((await auditApi.verify()).data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể kiểm tra tính toàn vẹn"));
    } finally { setVerifying(false); }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Nhật ký audit")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Ai đã làm gì, trên đối tượng nào và kết quả ra sao. Không hiển thị nội dung CV, ghi chú hay thông tin cá nhân.")}</Typography>
        </Box>
        <Button variant="outlined" startIcon={verifying ? <CircularProgress size={16} /> : <VerifiedUserIcon />} onClick={verify} disabled={verifying}>
          {t("Kiểm tra toàn vẹn nhật ký")}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {integrity && (
        <Alert severity={integrity.valid ? 'success' : 'error'} sx={{ mb: 2 }} onClose={() => setIntegrity(null)}>
          {integrity.valid
            ? t("Chuỗi băm toàn vẹn: đã kiểm tra {0} sự kiện, không phát hiện sửa đổi.", integrity.checked_events)
            : t("Phát hiện {0} sự kiện không khớp chuỗi băm trên tổng {1}. Cần báo IT/Security.", integrity.broken_events, integrity.checked_events)}
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select size="small" label={t("Loại thao tác")} value={actionType} sx={{ minWidth: 240 }}
          onChange={e => { setPage(0); setActionType(e.target.value); }}>
          <MenuItem value="">{t("Tất cả")}</MenuItem>
          {actionTypes.map(type => <MenuItem key={type} value={type}>{type}</MenuItem>)}
        </TextField>
        <TextField size="small" type="date" label={t("Từ ngày")} value={dateFrom} InputLabelProps={{ shrink: true }}
          onChange={e => { setPage(0); setDateFrom(e.target.value); }} />
        <TextField size="small" type="date" label={t("Đến ngày")} value={dateTo} InputLabelProps={{ shrink: true }}
          onChange={e => { setPage(0); setDateTo(e.target.value); }} />
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table size="small" aria-label={t("Nhật ký audit")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Thời gian")}</TableCell>
              <TableCell>{t("Người thực hiện")}</TableCell>
              <TableCell>{t("Loại thao tác")}</TableCell>
              <TableCell>{t("Đối tượng")}</TableCell>
              <TableCell>{t("Vị trí")}</TableCell>
              <TableCell>{t("Kết quả")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={6} align="center" sx={{ py: 6 }}><CircularProgress size={24} /></TableCell></TableRow>
            ) : items.length === 0 ? (
              <TableRow><TableCell colSpan={6} align="center" sx={{ py: 6, color: 'text.secondary' }}>{t("Không có sự kiện phù hợp")}</TableCell></TableRow>
            ) : items.map(event => (
              <TableRow key={event.event_id} hover>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{new Date(event.created_at).toLocaleString(dateLocale)}</TableCell>
                <TableCell>{event.actor_name || t("Hệ thống")}</TableCell>
                <TableCell><Typography variant="caption" fontFamily="monospace">{event.action_type}</Typography></TableCell>
                <TableCell>
                  <Typography variant="caption">{event.object_type}</Typography>
                  {event.object_id && <Typography variant="caption" display="block" color="text.secondary" fontFamily="monospace">{event.object_id.slice(0, 8)}</Typography>}
                </TableCell>
                <TableCell>{event.position_title ? `${event.position_title} · ${event.position_code}` : '—'}</TableCell>
                <TableCell>{event.outcome ? <Chip size="small" label={event.outcome} /> : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination component="div" count={total} page={page} rowsPerPage={pageSize}
          onPageChange={(_, next) => setPage(next)} rowsPerPageOptions={[25, 50, 100]}
          onRowsPerPageChange={e => { setPage(0); setPageSize(Number(e.target.value)); }}
          labelRowsPerPage={t("Số dòng mỗi trang")} />
      </TableContainer>
    </Box>
  );
}
