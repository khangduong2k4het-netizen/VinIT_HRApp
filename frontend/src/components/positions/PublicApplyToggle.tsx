'use client';

import * as React from 'react';
import { Alert, Box, Button, Card, CardContent, FormControlLabel, Link as MuiLink, Stack, Switch, Typography } from '@mui/material';
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
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <FormControlLabel
          control={<Switch checked={enabled} onChange={(_, next) => toggle(next)} disabled={saving} />}
          label={<Typography sx={{ fontWeight: 600 }}>{t('Nhận hồ sơ công khai qua trang /apply')}</Typography>}
        />
        <Box sx={{ mt: 1 }}>
          {enabled && portalEnabled && positionOpen && hasApprovedCriteria && (
            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
              <Typography variant="body2" color="text.secondary">
                {t('Ứng viên có thể nộp CV tại')}{' '}
                <MuiLink href={applyHref} target="_blank" rel="noopener">{applyHref}</MuiLink>
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
