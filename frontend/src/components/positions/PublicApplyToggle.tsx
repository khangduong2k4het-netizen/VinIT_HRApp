'use client';

import * as React from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, FormControlLabel, Link as MuiLink, Stack, Switch, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { positionsApi } from '@/lib/api';

interface PublicApplyToggleProps {
  positionId: string;
  positionCode?: string;
  enabled: boolean;
  portalEnabled: boolean;
  positionOpen: boolean;
  hasApprovedCriteria?: boolean;
  onChange: (enabled: boolean) => void;
}

// HR switch for the public /apply form of one position.
export default function PublicApplyToggle({
  positionId,
  positionCode,
  enabled,
  portalEnabled,
  positionOpen,
  hasApprovedCriteria = true,
  onChange,
}: PublicApplyToggleProps) {
  const { t } = useI18n();
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  const applyHref = positionCode ? `/apply?code=${encodeURIComponent(positionCode)}` : '/apply';
  const isLive = enabled && portalEnabled && positionOpen && hasApprovedCriteria;

  const copyLink = async () => {
    try {
      const fullUrl = `${window.location.origin}${applyHref}`;
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const toggle = async (next: boolean) => {
    setSaving(true);
    setError(null);
    try {
      const res = await positionsApi.setPublicApply(positionId, next);
      onChange(Boolean(res.data?.public_apply_enabled));
    } catch (err: any) {
      setError(err.response?.status === 403
        ? t('Chỉ HR Recruiter của vị trí này mới bật/tắt được nhận hồ sơ công khai.')
        : t('Không thể cập nhật trạng thái nhận hồ sơ công khai.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card sx={{ mb: 2.5 }}>
      <CardContent sx={{ py: 2 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" justifyContent="space-between" flexWrap="wrap" useFlexGap>
          <FormControlLabel
            sx={{ m: 0 }}
            control={<Switch checked={enabled} onChange={(_, next) => toggle(next)} disabled={saving} />}
            label={<Typography sx={{ fontWeight: 600, fontSize: 14, color: '#0F172A' }}>{t('Nhận hồ sơ công khai qua trang /apply')}</Typography>}
          />
          <Chip
            size="small"
            label={
              <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.7 }}>
                <Box component="span" aria-hidden sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: isLive ? '#12B76A' : '#94A3B8' }} />
                {isLive ? t('Đang công khai') : t('Chưa công khai')}
              </Box>
            }
            sx={{
              bgcolor: isLive ? '#ECFDF3' : '#F1F5F9',
              color: isLive ? '#067647' : '#475569',
              border: `1px solid ${isLive ? '#ABEFC6' : '#E2E8F0'}`,
              fontWeight: 600,
            }}
          />
        </Stack>
        <Box sx={{ mt: 1.25 }}>
          {isLive && (
            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="body2" color="text.secondary">
                {t('Ứng viên có thể nộp CV tại')}{' '}
                <MuiLink href={applyHref} target="_blank" rel="noopener" className="mono-code" sx={{ fontWeight: 600 }}>{applyHref}</MuiLink>
              </Typography>
              <Button size="small" variant="outlined" onClick={copyLink}>
                {copied ? t('Đã sao chép link') : t('Sao chép link ứng tuyển')}
              </Button>
            </Stack>
          )}
          {enabled && !positionOpen && (
            <Alert severity="info" sx={{ mt: 1 }}>{t('Vị trí không ở trạng thái Đang mở nên chưa hiện trên trang /apply.')}</Alert>
          )}
          {enabled && positionOpen && !hasApprovedCriteria && (
            <Alert severity="info" sx={{ mt: 1 }}>{t('Vị trí chưa có tiêu chí được duyệt cho JD mới nhất nên chưa hiện trên trang /apply.')}</Alert>
          )}
          {!portalEnabled && (
            <Alert severity="warning" sx={{ mt: 1 }}>{t('Cổng /apply đang tắt trên server (PUBLIC_INTAKE_ENABLED=false), nên ứng viên chưa nộp được dù đã bật ở đây.')}</Alert>
          )}
          {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
        </Box>
      </CardContent>
    </Card>
  );
}
