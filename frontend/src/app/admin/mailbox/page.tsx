'use client';

// F3.03 email channel: connect the Gmail recruiting mailbox. Admin only.
import * as React from 'react';
import { Suspense, useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, Stack, Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useSearchParams } from 'next/navigation';
import PageHeader from '@/components/common/PageHeader';
import { mailboxApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

const ERRORS: Record<string, string> = {
  STATE_INVALID: 'Phiên kết nối đã hết hạn hoặc không hợp lệ. Vui lòng bấm "Kết nối Gmail" lại.',
  ACCESS_DENIED: 'Bạn đã từ chối cấp quyền cho HRA trên trang Google.',
  NO_CODE: 'Google không trả về mã xác nhận. Vui lòng thử lại.',
  NOT_ADMIN: 'Chỉ Admin mới kết nối được hộp thư.',
  CODE_EXCHANGE_FAILED: 'Không đổi được mã xác nhận của Google. Kiểm tra GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET và địa chỉ chuyển hướng.',
  NO_REFRESH_TOKEN: 'Google không cấp khóa dùng lâu dài. Hãy gỡ quyền của ứng dụng trong tài khoản Google rồi kết nối lại.',
  SCOPES_NOT_GRANTED: 'Bạn chưa cấp đủ quyền (đọc thư và Pub/Sub). Hãy kết nối lại và tick đủ các quyền.',
  TOKEN_REVOKED: 'Quyền truy cập Gmail đã bị thu hồi hoặc hết hạn (ứng dụng ở chế độ Testing hết hạn sau 7 ngày). Hãy kết nối lại.',
  ENCRYPTION_KEY_MISSING: 'Server chưa cấu hình MAILBOX_ENCRYPTION_KEY.',
  GOOGLE_REFUSED: 'Google từ chối yêu cầu. Kiểm tra Gmail API, Pub/Sub và quyền của topic.',
};

type Status = {
  enabled: boolean; client_configured: boolean; encryption_ready: boolean;
  pubsub_topic: string | null; pubsub_subscription: string | null; redirect_uri: string;
  account: null | { email_address: string; status: string; last_error: string | null; last_sync_at: string | null;
    watch_expires_at: string | null; connected_at: string; address_example: string | null };
  last_30_days: Record<string, number>;
};

function MailboxAdmin() {
  const { t, dateLocale } = useI18n();
  const params = useSearchParams();
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setData((await mailboxApi.status()).data); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải trạng thái hộp thư.')); }
  }, [t]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const code = params.get('error');
    if (code) setError(t(ERRORS[code] || 'Kết nối không thành công.') + ` (${code})`);
    if (params.get('connected')) setNotice(t('Đã kết nối Gmail. HRA bắt đầu nhận CV gửi tới hộp thư này.'));
  }, [params, t]);

  const connect = async () => {
    try { setBusy('connect'); setError(null); window.location.href = (await mailboxApi.connectGmail()).data.auth_url; }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể bắt đầu kết nối.')); setBusy(null); }
  };
  const disconnect = async () => {
    try { setBusy('disconnect'); setError(null); await mailboxApi.disconnect(); setNotice(t('Đã ngắt kết nối hộp thư.')); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể ngắt kết nối.')); }
    finally { setBusy(null); }
  };
  const sync = async () => {
    try {
      setBusy('sync'); setError(null);
      const c = (await mailboxApi.syncNow()).data;
      setNotice(t('Đã đọc thư mới: {0} vào hồ sơ, {1} chờ phân loại, {2} bỏ qua.', c.MATCHED || 0, c.NEEDS_TRIAGE || 0, c.IGNORED || 0));
      await load();
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể đọc thư lúc này.')); }
    finally { setBusy(null); }
  };
  const copy = async (value: string) => { try { await navigator.clipboard.writeText(value); setNotice(t('Đã sao chép.')); } catch { /* ignore */ } };

  if (!data) return <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}>{error ? <Alert severity="error">{error}</Alert> : <CircularProgress size={28} />}</Box>;
  const account = data.account;
  const checks: [boolean, string][] = [
    [data.enabled, t('Bật GMAIL_INTAKE_ENABLED=true trong backend/.env')],
    [data.client_configured, t('Điền GMAIL_CLIENT_ID và GMAIL_CLIENT_SECRET (OAuth client trên Google Cloud)')],
    [data.encryption_ready, t('Điền MAILBOX_ENCRYPTION_KEY (khóa Fernet) để mã hóa quyền truy cập Gmail')],
    [!!data.pubsub_topic, t('Điền GMAIL_PUBSUB_TOPIC để Gmail báo ngay khi có thư')],
    [!!data.pubsub_subscription, t('Điền GMAIL_PUBSUB_SUBSCRIPTION để HRA nhận thông báo')],
    [!!account && account.status === 'ACTIVE', t('Kết nối tài khoản Gmail bằng nút bên dưới')],
  ];
  const stats = [
    { label: t('Đã vào hồ sơ'), value: data.last_30_days.MATCHED || 0, color: 'success.main' },
    { label: t('Chờ phân loại'), value: data.last_30_days.NEEDS_TRIAGE || 0, color: 'warning.main' },
    { label: t('Bỏ qua'), value: data.last_30_days.IGNORED || 0, color: 'text.secondary' },
    { label: t('Lỗi'), value: data.last_30_days.FAILED || 0, color: 'error.main' },
  ];

  return (
    <Box>
      <PageHeader
        eyebrow={t('Quản trị')}
        title={t('Kết nối hộp thư nhận CV')}
        description={t('CV gửi tới hộp thư Gmail này được tự động đưa vào HRA. Thư gửi tới địa chỉ có mã vị trí (ví dụ ten+REQ-IT-043@gmail.com) hoặc có mã vị trí trong tiêu đề sẽ vào đúng vị trí; thư không rõ vị trí nằm trong "Hộp thư CV" chờ HR phân loại.')}
      />
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {stats.map(stat => (
          <Grid item xs={6} sm={3} key={stat.label}>
            <Card variant="outlined">
              <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
                <Typography variant="caption" color="text.secondary">{stat.label} ({t('30 ngày qua')})</Typography>
                <Typography variant="h4" className="tabular-nums" sx={{ mt: 0.5, fontWeight: 700, color: stat.color }}>
                  {stat.value}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="stretch">
        <Card variant="outlined" sx={{ flex: 1, minWidth: 0 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>{t('Hộp thư')}</Typography>
            {account ? (
              <Stack spacing={1.25}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Typography fontWeight={600} sx={{ wordBreak: 'break-all' }}>{account.email_address}</Typography>
                  <Chip size="small" label={account.status === 'ACTIVE' ? t('Đang nhận thư') : account.status === 'ERROR' ? t('Lỗi, cần kết nối lại') : t('Đã ngắt')}
                    color={account.status === 'ACTIVE' ? 'success' : account.status === 'ERROR' ? 'error' : 'default'} />
                </Stack>
                {account.last_error && <Alert severity="warning">{t(ERRORS[account.last_error] || 'Lần đọc thư gần nhất bị lỗi.')} ({account.last_error})</Alert>}
                <Typography variant="body2" color="text.secondary">
                  {t('Đọc thư lần cuối')}: {account.last_sync_at ? new Date(account.last_sync_at).toLocaleString(dateLocale) : t('chưa có')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {t('Gmail báo thư mới đến hết')}: {account.watch_expires_at ? new Date(account.watch_expires_at).toLocaleString(dateLocale) : t('chưa bật (sẽ đọc định kỳ mỗi phút)')}
                </Typography>
                {account.address_example && (
                  <Box sx={{ p: 1.5, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>{t('Địa chỉ nhận CV cho từng vị trí, ví dụ REQ-IT-043:')}</Typography>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography component="code" className="mono-code" sx={{ wordBreak: 'break-all' }}>{account.address_example}</Typography>
                      <Button size="small" startIcon={<ContentCopyIcon fontSize="small" />} onClick={() => copy(account.address_example!)}>{t('Sao chép')}</Button>
                    </Stack>
                  </Box>
                )}
              </Stack>
            ) : <Typography color="text.secondary">{t('Chưa kết nối hộp thư nào.')}</Typography>}
            <Stack direction="row" spacing={1} sx={{ mt: 2.5 }} flexWrap="wrap" useFlexGap>
              <Button variant="contained" color="secondary" onClick={connect} disabled={!!busy || !data.enabled || !data.client_configured || !data.encryption_ready}>
                {busy === 'connect' ? <CircularProgress size={18} color="inherit" /> : account ? t('Kết nối lại Gmail') : t('Kết nối Gmail')}
              </Button>
              {account && account.status !== 'DISCONNECTED' && <>
                <Button variant="outlined" onClick={sync} disabled={!!busy}>{busy === 'sync' ? <CircularProgress size={18} /> : t('Đọc thư ngay')}</Button>
                <Button color="error" onClick={disconnect} disabled={!!busy}>{t('Ngắt kết nối')}</Button>
              </>}
            </Stack>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1, minWidth: 0 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1.5 }}>{t('Cấu hình cần có')}</Typography>
            <Stack spacing={1.25}>
              {checks.map(([ok, label]) => (
                <Stack key={label} direction="row" spacing={1} alignItems="flex-start">
                  {ok ? <CheckCircleOutlineIcon color="success" fontSize="small" /> : <RadioButtonUncheckedIcon color="disabled" fontSize="small" />}
                  <Typography variant="body2">{label}</Typography>
                </Stack>
              ))}
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2, wordBreak: 'break-all' }}>
              {t('Địa chỉ chuyển hướng cần khai báo trên Google Cloud')}: <code>{data.redirect_uri}</code>
            </Typography>
          </CardContent>
        </Card>
      </Stack>
    </Box>
  );
}

// useSearchParams needs a Suspense boundary for the static build.
export default function MailboxAdminPage() {
  return <Suspense fallback={<CircularProgress size={24} />}><MailboxAdmin /></Suspense>;
}
