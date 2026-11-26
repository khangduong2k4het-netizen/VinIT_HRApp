'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Grid, LinearProgress, Skeleton,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import PeopleOutlineIcon from '@mui/icons-material/PeopleOutline';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import RefreshIcon from '@mui/icons-material/Refresh';
import { dashboardApi } from '@/lib/api';
import { getCurrentUser } from '@/lib/meCache';
import { clearUxEvents, readUxEvents, summarizeUxImpact, type UxEvent } from '@/lib/uxMetrics';
import { increasesSince, readWorkQueueSnapshot, snapshotWorkQueue, totalNewWork, writeWorkQueueSnapshot, type WorkQueueIncrease } from '@/lib/workQueueDigest';
import { workQueueTypeAction, workQueueTypeLabel } from '@/lib/workQueueLabels';
import { APPLICATION_STATUSES, type ApplicationStatus } from '@/lib/applicationStatus';
import StatusBadge from '@/components/common/StatusBadge';
import PageHeader from '@/components/common/PageHeader';
import WorkQueueList from '@/components/workflow/WorkQueueList';
import ScorecardReminders from '@/components/shortlist/ScorecardReminders';
import type { WorkQueueResponse } from '@/types';

interface DashboardSummary {
  open_positions: number;
  /** Vị trí OPEN nhưng đã quá hạn ứng tuyển: cổng đã đóng, không nhận hồ sơ. */
  open_positions_deadline_passed?: number;
  total_applications: number;
  applications_by_status: Record<ApplicationStatus, number>;
  applications_processing: number;
  files_needing_hr_review: number;
  files_needing_review_rate: number | null;
  duplicate_alerts: number;
  assessments_completed: number;
  average_coverage: number | null;
  coverage_sample_size: number;
  coverage_under_threshold: number;
}

const percent = (value: number | null | undefined) =>
  value == null ? '—' : `${Math.round(value * 100)}%`;

export default function DashboardPage() {
  const { t } = useI18n();
  const [hrAccess, setHrAccess] = useState<boolean | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [workQueue, setWorkQueue] = useState<WorkQueueResponse | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reminderRefresh, setReminderRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Số đo tác động UX nằm trong localStorage của máy này: đọc sau khi mount để
  // không lệch hydration, và không trộn với số liệu máy chủ trong cùng một con số.
  const [uxEvents, setUxEvents] = useState<UxEvent[]>([]);
  useEffect(() => { setUxEvents(readUxEvents()); }, []);
  // "Có gì mới từ lần trước": so lần tải này với mốc đã chụp lần trước. Chỉ tính
  // một lần cho mỗi lần mở trang để Strict Mode/đếm lại không xoá mất dấu vết.
  const [newWorkSinceLastVisit, setNewWorkSinceLastVisit] = useState<WorkQueueIncrease[]>([]);
  const digestCaptured = useRef(false);
  const ux = summarizeUxImpact(uxEvents);
  const uxMinutes = (value: number | null) => (value == null ? t('Chưa có số đo') : t('{0} phút', value < 1 ? '<1' : String(value)));

  const loadData = useCallback(async (initial = false) => {
    try {
      if (initial) setLoading(true); else { setRefreshing(true); setReminderRefresh(n => n + 1); }
      setError(null);
      setQueueError(null);
      const [summaryResponse, queueResponse, meResponse] = await Promise.allSettled([
        dashboardApi.getSummary(),
        dashboardApi.getWorkQueue(),
        getCurrentUser(),
      ]);
      if (meResponse.status === 'fulfilled') {
        const me = meResponse.value;
        setHrAccess(Boolean(me.system_roles?.some((role: string) => ['ADMIN', 'HR_LEAD', 'HR_RECRUITER'].includes(role)) || me.position_assignments?.some((a: any) => ['HR_LEAD', 'HR_RECRUITER'].includes(a.position_role))));
      } else setHrAccess(null);
      if (summaryResponse.status === 'fulfilled') {
        setSummary(summaryResponse.value.data);
      } else {
        const err: any = summaryResponse.reason;
        setError(err.response?.data?.detail || t("Không thể tải dữ liệu tổng hợp. Vui lòng thử lại."));
      }
      if (queueResponse.status === 'fulfilled') {
        setWorkQueue(queueResponse.value.data);
      } else {
        const err: any = queueResponse.reason;
        setQueueError(err.response?.data?.detail || t("Không thể tải hàng đợi công việc. Vui lòng thử lại."));
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t("Không thể tải dữ liệu tổng hợp. Vui lòng thử lại."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [t]);

  useEffect(() => { loadData(true); }, [loadData]);

  useEffect(() => {
    if (!workQueue || digestCaptured.current) return;
    digestCaptured.current = true;
    setNewWorkSinceLastVisit(increasesSince(readWorkQueueSnapshot(), workQueue.items));
    // Chụp lại ngay sau khi so: lần mở dashboard sau sẽ so với chính lần này.
    writeWorkQueueSnapshot(snapshotWorkQueue(workQueue.items));
  }, [workQueue]);

  const cards = summary ? [
    { label: t("Vị trí đang mở"), value: summary.open_positions, icon: <WorkOutlineIcon />, color: '#134D8B', bg: '#EAF3FC', href: '/positions?status=OPEN', hint: t('Xem vị trí đang mở'), note: (summary.open_positions_deadline_passed ?? 0) > 0 ? t('{0} vị trí đã quá hạn, không nhận hồ sơ', summary.open_positions_deadline_passed) : undefined },
    { label: t("Tổng hồ sơ"), value: summary.total_applications, icon: <PeopleOutlineIcon />, color: '#0A2B57', bg: '#EAF3FC', href: '/positions', hint: t('Chọn vị trí để xem hồ sơ') },
    { label: t("CV cần HR kiểm tra"), value: summary.files_needing_hr_review, icon: <WarningAmberIcon />, color: '#B54708', bg: '#FFFAEB', href: '#work-queue', hint: t('Xem công việc cần kiểm tra') },
    { label: t("Đã shortlist"), value: summary.applications_by_status.SHORTLIST, icon: <FactCheckOutlinedIcon />, color: '#067647', bg: '#ECFDF3', href: hrAccess ? '/positions' : '/shortlist', hint: hrAccess ? t('Chọn vị trí để xem ứng viên shortlist') : t('Xem chia sẻ và phản hồi') },
  ] : [];

  return (
    <Box>
      <PageHeader
        eyebrow={t("HÀNG ĐỢI CÔNG VIỆC")}
        title={t("Tổng quan công việc")}
        description={t("Bắt đầu từ việc cần xử lý, sau đó xem số liệu tổng quan theo phạm vi bạn được phép xem.")}
        actions={(
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => loadData()} disabled={refreshing || loading}>
            {refreshing ? t("Đang cập nhật…") : t("Làm mới")}
          </Button>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" onClick={() => loadData(!summary)}>{t("Thử lại")}</Button>}>{t(error)}</Alert>}
      {loading && (
        <Grid container spacing={2} aria-label={t("Đang tải số liệu")}>
          {[0, 1, 2, 3].map(n => <Grid item xs={12} sm={6} lg={3} key={n}><Skeleton variant="rounded" height={130} /></Grid>)}
          <Grid item xs={12}><Skeleton variant="rounded" height={260} /></Grid>
        </Grid>
      )}
      {!loading && summary && (
        <>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {cards.map(card => (
              <Grid item xs={12} sm={6} lg={3} key={card.label}>
                <Card sx={{ height: '100%', border: '1px solid #E9EEF4', boxShadow: '0 2px 10px rgba(10,43,87,.04)' }}>
                  <CardActionArea component={Link} href={card.href} aria-label={`${card.label}: ${card.hint}`}><CardContent sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 2 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">{card.label}</Typography>
                      <Typography variant="h3" sx={{ mt: 1, fontSize: 30, fontWeight: 700, color: card.color }}>{card.value}</Typography>
                      {card.note && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, maxWidth: 190 }}>{card.note}</Typography>}
                    </Box>
                    <Box sx={{ display: 'grid', placeItems: 'center', width: 42, height: 42, borderRadius: 2, bgcolor: card.bg, color: card.color }}>
                      {card.icon}
                    </Box>
                  </CardContent></CardActionArea>
                </Card>
              </Grid>
            ))}
          </Grid>

          {summary.total_applications === 0 && (
            <Alert severity="info" sx={{ mb: 3 }} action={<Button component={Link} href="/positions" color="inherit">{t("Xem vị trí")}</Button>}>{t("Chưa có hồ sơ trong phạm vi bạn được phép xem. Hãy bắt đầu từ một vị trí tuyển dụng.")}</Alert>
          )}

          <ScorecardReminders refreshKey={reminderRefresh} />
          <Box id="work-queue" sx={{ mb: 4, scrollMarginTop: 90 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 2, flexWrap: 'wrap', mb: 2 }}>
              <Box>
                <Typography variant="h2" sx={{ fontSize: 19, color: '#0A2B57' }}>{t("Việc cần làm")}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {workQueue
                    ? t("{0} vị trí cần chú ý · {1} file cần kiểm tra · {2} hồ sơ cần xác minh", workQueue.summary.positions_needing_attention, workQueue.summary.files_needing_review, workQueue.summary.applications_needing_verification)
                    : t("Danh sách việc theo từng vị trí và hành động tiếp theo.")}
                </Typography>
                {/* Chỉ hiện khi thật sự có việc: dòng "0 việc" chỉ làm loãng màn hình. */}
                {workQueue && (workQueue.summary.positions_deadline_passed ?? 0) + (workQueue.summary.positions_deadline_soon ?? 0) > 0 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {t("{0} vị trí đã quá hạn ứng tuyển · {1} vị trí sắp hết hạn", workQueue.summary.positions_deadline_passed ?? 0, workQueue.summary.positions_deadline_soon ?? 0)}
                  </Typography>
                )}

                {/* Tuổi hồ sơ: null nghĩa là chưa đo được, không phải 0 ngày. */}
                {workQueue && workQueue.summary.oldest_waiting_days != null && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {t("{0} hồ sơ chờ quá {1} ngày · lâu nhất {2} ngày", workQueue.summary.applications_waiting_over_threshold ?? 0, workQueue.summary.waiting_attention_days ?? 7, workQueue.summary.oldest_waiting_days)}
                  </Typography>
                )}
              </Box>
              {workQueue && <Chip label={t("Cập nhật theo quyền truy cập")} size="small" variant="outlined" />}
            </Box>
            {/* Việc mới kể từ lần mở trước. Đây là câu trả lời cho "có gì đổi từ
                hôm qua" mà không cần thêm backend: chính hàng đợi đã đủ dữ liệu. */}
            {newWorkSinceLastVisit.length > 0 && (
              <Alert severity="info" data-testid="work-queue-digest" sx={{ mb: 2 }}>
                <Typography variant="body2" fontWeight={600}>
                  {t('Có {0} việc mới kể từ lần mở trước.', totalNewWork(newWorkSinceLastVisit))}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {newWorkSinceLastVisit.slice(0, 3).map(item => (
                    `${t(workQueueTypeLabel({ type: item.type }))}${item.positionTitle ? ` · ${item.positionTitle}` : ''} (+${item.added})`
                  )).join('  ·  ')}
                </Typography>
              </Alert>
            )}
            {queueError && <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => loadData()}>{t("Thử lại")}</Button>}>{t(queueError)}</Alert>}
            {/* Việc đã kiểm xong nằm trong cụm "Đã quyết" của danh sách: nếu chỉ
                hiện "cần xác minh" thì con số nhỏ đi mỗi lần HR làm việc, và không
                ai phân biệt được "đã xử lý" với "dữ liệu biến mất". */}
            {/* Việc của chính người dùng (buổi hôm nay, phiếu quá hạn) đứng trên
                danh sách theo vị trí: nếu có buổi chiều nay thì đó là việc gấp
                nhất trong ngày, không phải một dòng nằm lẫn giữa việc của vị trí.
                Đây là danh sách riêng chứ không phải item của `items` — xem
                `WorkQueueResponse.interview_work` để biết vì sao. */}
            {(workQueue?.interview_work?.length ?? 0) > 0 && (
              <Stack spacing={1} sx={{ mb: 2 }}>
                {workQueue!.interview_work!.map(item => (
                  <Card key={item.item_id} variant="outlined" sx={{ borderColor: '#E4EAF2' }}>
                    <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', py: 1.5 }}>
                      <Box sx={{ minWidth: 220, flex: 1 }}>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Chip size="small" variant="outlined"
                            label={t(item.priority === 'HIGH' ? 'Cao' : 'Trung bình')}
                            color={item.priority === 'HIGH' ? 'error' : 'warning'} />
                          <Typography variant="body1" fontWeight={700} color="#0A2B57">
                            {t(workQueueTypeLabel({ type: item.type }))}
                          </Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          {t('Gắn với chính bạn, không thuộc vị trí nào')}
                        </Typography>
                      </Box>
                      <Typography variant="h3" sx={{ fontSize: 24, minWidth: 48, textAlign: 'center', color: item.priority === 'HIGH' ? '#B42318' : '#0A2B57' }}>
                        {item.count}
                      </Typography>
                      <Button component={Link} href={`${item.target.pathname}${item.target.search ? `?${item.target.search}` : ''}`}
                        variant={item.priority === 'HIGH' ? 'contained' : 'outlined'} size="small">
                        {t(workQueueTypeAction({ type: item.type }))}
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            )}
            {workQueue
              ? <WorkQueueList items={workQueue.items} doneCount={workQueue.summary.applications_verification_complete ?? 0} />
              : !queueError ? <Skeleton variant="rounded" height={180} /> : null}
          </Box>

          <Typography variant="h2" sx={{ fontSize: 19, color: '#0A2B57', mb: 2 }}>{t("Tổng quan phân tích")}</Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card sx={{ height: '100%', border: '1px solid #E9EEF4' }}>
                <CardContent>
                  <Typography variant="h2" sx={{ fontSize: 18, color: '#0A2B57' }}>{t("Trạng thái hồ sơ")}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>{t("Các giai đoạn do HR cập nhật")}</Typography>
                  <TableContainer>
                    <Table size="small" aria-label={t("Phân bố trạng thái hồ sơ")}>
                      <TableHead><TableRow><TableCell>{t("Trạng thái")}</TableCell><TableCell align="right">{t("Số hồ sơ")}</TableCell></TableRow></TableHead>
                      <TableBody>
                        {(Object.keys(APPLICATION_STATUSES) as ApplicationStatus[]).map(code => (
                          <TableRow key={code}>
                            <TableCell><StatusBadge type={APPLICATION_STATUSES[code].badge} label={t(APPLICATION_STATUSES[code].label)} /></TableCell>
                            <TableCell align="right" sx={{ fontWeight: 600 }}>{summary.applications_by_status[code] ?? 0}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card sx={{ height: '100%', border: '1px solid #E9EEF4' }}>
                <CardContent>
                  <Typography variant="h2" sx={{ fontSize: 18, color: '#0A2B57' }}>{t("Chất lượng xử lý")}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 3 }}>{t("Tính theo hồ sơ trong phạm vi được phân quyền")}</Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 1 }}>
                    <Typography variant="body2">{t("Độ phủ bằng chứng trung bình")}</Typography>
                    <Typography variant="body2" fontWeight={700}>{percent(summary.average_coverage)}</Typography>
                  </Box>
                  {summary.average_coverage != null && <LinearProgress variant="determinate" value={Math.min(100, summary.average_coverage * 100)} sx={{ height: 7, borderRadius: 4, mb: 1 }} />}
                  <Typography variant="caption" color="text.secondary">
                    {summary.coverage_sample_size ? t("Từ đánh giá hoàn tất gần nhất của {0} hồ sơ.", summary.coverage_sample_size) : t("Chưa có đánh giá hoàn tất để tính độ phủ.")}
                  </Typography>
                  <Box sx={{ mt: 3, display: 'grid', gap: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                      <Typography variant="body2">{t("Hồ sơ có độ phủ dưới 70%")}</Typography>
                      <Typography variant="body2" fontWeight={700}>{summary.coverage_under_threshold}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                      <Typography variant="body2">{t("Tỷ lệ CV cần HR kiểm tra")}</Typography>
                      <Typography variant="body2" fontWeight={700}>{percent(summary.files_needing_review_rate)}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                      <Typography variant="body2"><ContentCopyIcon sx={{ fontSize: 15, verticalAlign: 'text-bottom', mr: 0.5 }} />{t("Hồ sơ có cảnh báo trùng")}</Typography>
                      <Typography variant="body2" fontWeight={700}>{summary.duplicate_alerts}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                      <Typography variant="body2">{t("Hồ sơ đang xử lý CV")}</Typography>
                      <Chip label={summary.applications_processing} size="small" color={summary.applications_processing ? 'info' : 'default'} />
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                      <Typography variant="body2">{t("Hồ sơ đã được đánh giá")}</Typography>
                      <Typography variant="body2" fontWeight={700}>{summary.assessments_completed}</Typography>
                    </Box>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 3 }}>{t("Cảnh báo trùng là số hồ sơ có ít nhất một tín hiệu chưa xử lý, không phải số cặp trùng.")}</Typography>
                </CardContent>
              </Card>
            </Grid>
            {/* Đo chính các cải tiến UX: thời gian HR ở trong hồ sơ, từ mở tới hoàn
                tất và mức dùng lô. Chỉ số đo cục bộ của trình duyệt này; số hồ sơ
                quá hạn là số toàn hệ thống và đã hiện một lần ở "Việc cần làm"
                phía trên, nên không lặp lại ở đây. */}
            <Grid item xs={12}>
              <Card data-testid="ux-impact" sx={{ border: '1px solid #E9EEF4' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    <Box>
                      <Typography variant="h2" sx={{ fontSize: 18, color: '#0A2B57' }}>{t('Tác động của cải tiến UX')}</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 760 }}>
                        {t('Đo trên trình duyệt này: mở/rời hồ sơ, hoàn tất hồ sơ và các lô hành động. Không ghi tên, CV hay nội dung hồ sơ.')}
                      </Typography>
                    </Box>
                    <Button size="small" data-testid="ux-clear" onClick={() => { clearUxEvents(); setUxEvents([]); }} disabled={!uxEvents.length}>{t('Xoá số đo')}</Button>
                  </Box>
                  <Grid container spacing={3} sx={{ mt: 0.5 }}>
                    <Grid item xs={12} sm={6} md={4}>
                      <Typography variant="body2" color="text.secondary">{t('Thời gian xem hồ sơ trung bình')}</Typography>
                      <Typography variant="h3" data-testid="ux-median-dwell" sx={{ mt: 0.5, fontSize: 24, fontWeight: 700, color: '#0A2B57' }}>{uxMinutes(ux.medianDwellMinutes)}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {t('Trung vị {0} lượt mở hồ sơ đã rời.', ux.profileCloses - ux.ignoredDwellCount)}
                        {ux.ignoredDwellCount > 0 ? ` · ${t('Bỏ qua {0} lượt dài hơn 30 phút (tab để quên).', ux.ignoredDwellCount)}` : ''}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6} md={4}>
                      <Typography variant="body2" color="text.secondary">{t('Thời gian từ mở đến hoàn tất')}</Typography>
                      <Typography variant="h3" data-testid="ux-completion" sx={{ mt: 0.5, fontSize: 24, fontWeight: 700, color: '#0A2B57' }}>{uxMinutes(ux.averageCompletionMinutes)}</Typography>
                      <Typography variant="caption" color="text.secondary">{t('{0} hồ sơ đã hoàn tất trên trình duyệt này.', ux.verifiedProfiles)}</Typography>
                    </Grid>
                    {/* Số hồ sơ quá hạn chỉ hiện ở "Việc cần làm" phía trên: một
                        con số máy chủ, một chỗ hiển thị. */}
                    <Grid item xs={12} sm={6} md={4}>
                      <Typography variant="body2" color="text.secondary">{t('Lô hành động đã dùng')}</Typography>
                      <Typography variant="h3" data-testid="ux-bulk" sx={{ mt: 0.5, fontSize: 24, fontWeight: 700, color: '#0A2B57' }}>{ux.bulkRuns}</Typography>
                      <Typography variant="caption" color="text.secondary">{t('{0} hồ sơ · {1} lỗi · trung bình {2}', ux.bulkRecords, ux.bulkFailedRecords, uxMinutes(ux.bulkAverageMinutes))}</Typography>
                    </Grid>
                  </Grid>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                    {ux.sampleSince
                      ? t('Đo từ {0}.', new Date(ux.sampleSince).toLocaleString('vi-VN'))
                      : t('Chưa có số đo nào: số liệu xuất hiện sau khi bạn mở hồ sơ hoặc chạy một lô.')}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
}
