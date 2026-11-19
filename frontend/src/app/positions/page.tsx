'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Chip,
  CircularProgress,
  Alert,
  TextField,
  InputAdornment,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SearchIcon from '@mui/icons-material/Search';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { positionsApi, dashboardApi, authApi } from '@/lib/api';
import StatusBadge from '@/components/common/StatusBadge';
import { Position } from '@/types';

export default function PositionsPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [positions, setPositions] = useState<Position[]>([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applicationTotal, setApplicationTotal] = useState<number | null>(null);
  const [canCreate, setCanCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const loadPositions = useCallback(async () => {
    try {
      setLoading(true);
      const [positions, stats, me] = await Promise.all([
        positionsApi.listAll(), dashboardApi.getSummary().catch(() => null), authApi.me(),
      ]);
      setCanCreate(me.data.system_roles?.some((role: string) => ['ADMIN', 'HR_LEAD', 'HR_RECRUITER'].includes(role)) ||
        me.data.position_assignments?.some((a: any) => ['HR_RECRUITER', 'HR_LEAD'].includes(a.position_role)) || false);
      setPositions(positions);
      setError(null);
      setApplicationTotal(stats?.data?.total_applications ?? null);
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải danh sách vị trí"));
    } finally {
      setLoading(false);
    }
  }, [t]);
  useEffect(() => { loadPositions(); }, [loadPositions]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    if (status && ['OPEN', 'PAUSED', 'CLOSED'].includes(status)) setStatusFilter(status);
    setSearchQuery(params.get('q') || '');
  }, []);

  // Search covers title and code: HR knows "REQ-014" as often as the job title.
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const matchesSearch = (position: Position) => !normalizedQuery
    || String(position.title || '').toLowerCase().includes(normalizedQuery)
    || String(position.position_code || '').toLowerCase().includes(normalizedQuery);
  const statusCounts = {
    ALL: positions.length,
    OPEN: positions.filter(p => p.status === 'OPEN').length,
    PAUSED: positions.filter(p => p.status === 'PAUSED').length,
    CLOSED: positions.filter(p => p.status === 'CLOSED').length,
  };
  const visiblePositions = positions.filter(p => (statusFilter === 'ALL' || p.status === statusFilter) && matchesSearch(p));
  const syncUrl = (status: string, search: string) => {
    const params = new URLSearchParams();
    if (status !== 'ALL') params.set('status', status);
    if (search.trim()) params.set('q', search.trim());
    const query = params.toString();
    window.history.replaceState(null, '', `/positions${query ? `?${query}` : ''}`);
  };
  const selectStatus = (status: string) => { setStatusFilter(status); syncUrl(status, searchQuery); };
  const changeSearch = (value: string) => { setSearchQuery(value); syncUrl(statusFilter, value); };
  const clearPositionFilters = () => { setStatusFilter('ALL'); setSearchQuery(''); syncUrl('ALL', ''); };


  const getPositionStatusBadge = (status: string) => {
    switch (status) {
      case 'OPEN':
        return <StatusBadge type="position-open" label={t("Đang mở")} />;
      case 'PAUSED':
        return <StatusBadge type="position-paused" label={t("Tạm dừng")} />;
      case 'CLOSED':
        return <StatusBadge type="position-closed" label={t("Đã đóng")} />;
      default:
        return null;
    }
  };

  const getCriteriaBadge = (pos: Position) => {
    const labels: Record<string, string> = {
      DRAFT: t("Bản nháp"), PENDING_HR_REVIEW: t("Chờ HR duyệt"),
      PENDING_HM_APPROVAL: t("Chờ HM duyệt"), APPROVED: t("Đã duyệt"), REJECTED: t("Từ chối"),
    };
    const label = pos.criteria_status ? (labels[pos.criteria_status] || t("Chưa rõ")) : t("Chưa có");
    const description = pos.criteria_approved && pos.criteria_status !== 'APPROVED'
      ? t("Phiên bản mới nhất chưa hoàn tất; vẫn có phiên bản trước đã duyệt.")
      : t("Trạng thái của phiên bản tiêu chí mới nhất");
    return (
      <Tooltip title={description}>
        <span><StatusBadge type={pos.criteria_status === 'APPROVED' ? 'criteria-approved' : 'criteria-draft'} label={label} /></span>
      </Tooltip>
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}>
        <CircularProgress color="secondary" />
      </Box>
    );
  }

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 4 }}>
        <Box>
          <Typography variant="h1" sx={{ fontSize: 28, color: '#0A2B57', mb: 0.5 }}>{t("Danh sách vị trí tuyển dụng")}</Typography>
          <Typography variant="body2" color="text.secondary">{t("Quản lý các vị trí đang tuyển, tiêu chí đánh giá và hồ sơ ứng viên")}</Typography>
        </Box>
        {canCreate && <Button
          variant="contained"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={() => router.push('/positions/new')}
          size="large"
        >{t("Tạo vị trí mới")}</Button>}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={loadPositions}>{t("Thử lại")}</Button>}>
          {t(error)}
        </Alert>
      )}

      {!error && <>
      {/* Summary Cards */}
      <Grid container spacing={{ xs: 2, sm: 3 }} sx={{ mb: 4 }}>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Vị trí đang mở")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {positions.filter(p => p.status === 'OPEN').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Tạm dừng")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#B54708', mt: 1 }}>
                {positions.filter(p => p.status === 'PAUSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Đã đóng")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#475569', mt: 1 }}>
                {positions.filter(p => p.status === 'CLOSED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="caption" color="text.secondary">{t("Tổng hồ sơ")}</Typography>
              <Typography variant="h3" sx={{ fontSize: 24, fontWeight: 'bold', color: '#0A2B57', mt: 1 }}>
                {applicationTotal ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap', alignItems: 'center' }} role="group" aria-label={t("Lọc vị trí")}>
        {([['ALL','Tất cả'],['OPEN','Đang mở'],['PAUSED','Tạm dừng'],['CLOSED','Đã đóng']] as const).map(([value,label]) => (
          <Chip
            key={value}
            label={`${t(label)} (${statusCounts[value]})`}
            onClick={() => selectStatus(value)}
            aria-pressed={statusFilter === value}
            // `color` alone left every chip looking identical, so a link like
            // /positions?status=CLOSED rendered "0/1 vị trí" under four chips that
            // all looked unselected — the filter was applied but invisible. The
            // selected chip is now filled; the rest stay outlined.
            variant={statusFilter === value ? 'filled' : 'outlined'}
            sx={statusFilter === value
              ? { backgroundColor: '#0A2B57', color: '#fff', fontWeight: 700, '&:hover': { backgroundColor: '#134D8B' } }
              : undefined}
          />
        ))}
        <TextField
          size="small"
          value={searchQuery}
          onChange={e => changeSearch(e.target.value)}
          placeholder={t("Tìm theo tên hoặc mã vị trí")}
          inputProps={{ 'aria-label': t("Tìm theo tên hoặc mã vị trí") }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" sx={{ color: '#A09F9C' }} /></InputAdornment> }}
          sx={{ minWidth: 260, ml: { xs: 0, sm: 'auto' } }}
        />
        {(normalizedQuery || statusFilter !== 'ALL') && (
          <Button size="small" onClick={clearPositionFilters}>{t("Xoá bộ lọc và tìm kiếm")}</Button>
        )}
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }} data-testid="position-count">
        {t("Hiển thị {0}/{1} vị trí.", visiblePositions.length, positions.length)}
        {normalizedQuery ? ` · ${t("Đang lọc theo: “{0}”.", searchQuery.trim())}` : ''}
      </Typography>
      {/* On small screens cards keep the actions and status visible without horizontal scrolling. */}
      <Box sx={{ display: { xs: 'grid', md: 'none' }, gap: 2 }}>
        {visiblePositions.length === 0 ? (
          <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>{positions.length ? t("Không có vị trí nào khớp bộ lọc hoặc tìm kiếm.") : t("Chưa có vị trí trong phạm vi của bạn")}</Paper>
        ) : visiblePositions.map(pos => (
          <Card key={pos.position_id} sx={{ border: '1px solid #E9EEF4' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#0A2B57', overflowWrap: 'anywhere' }}>{pos.title}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{pos.position_code} · {pos.department_name || pos.org_unit || t("Chưa có đơn vị")}</Typography>
                </Box>
                {getPositionStatusBadge(pos.status)}
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 2 }}>
                <Box><Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>{t("Tiêu chí mới nhất")}</Typography>{getCriteriaBadge(pos)}</Box>
                <Button variant="outlined" size="small" onClick={() => router.push(`/positions/${pos.position_id}`)} aria-label={t("Xem vị trí {0}", pos.title)}>{t("Xem vị trí")}</Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      {/* Wider screens retain the compact table. */}
      <TableContainer component={Paper} sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
        <Table aria-label={t("Danh sách vị trí tuyển dụng")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("Mã vị trí")}</TableCell>
              <TableCell>{t("Tên vị trí")}</TableCell>
              <TableCell>{t("Đơn vị")}</TableCell>
              <TableCell>{t("Trạng thái")}</TableCell>
              <TableCell>{t("Tiêu chí mới nhất")}</TableCell>
              <TableCell align="right">{t("Thao tác")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visiblePositions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8, color: 'text.secondary' }}>{positions.length ? t("Không có vị trí nào khớp bộ lọc hoặc tìm kiếm.") : t("Chưa có vị trí nào được tạo")}</TableCell>
              </TableRow>
            ) : (
              visiblePositions.map((pos) => (
                <TableRow key={pos.position_id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                      {pos.position_code}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Button onClick={() => router.push(`/positions/${pos.position_id}`)} sx={{ textAlign: 'left', p: 0, textTransform: 'none' }}>{pos.title}</Button>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{pos.department_name || pos.org_unit || '-'}</Typography>
                  </TableCell>
                  <TableCell>{getPositionStatusBadge(pos.status)}</TableCell>
                  <TableCell>
                    {getCriteriaBadge(pos)}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      color="primary"
                      onClick={() => router.push(`/positions/${pos.position_id}`)}
                      sx={{ color: '#0A2B57' }}
                      aria-label={t("Xem vị trí {0}", pos.title)}
                    >
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      </>}


    </Box>
  );
}
