'use client';

import * as React from 'react';
import { Alert, Box, Card, CardContent, FormControlLabel, Link as MuiLink, Switch, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { positionsApi } from '@/lib/api';

interface PublicApplyToggleProps {
  positionId: string;
  enabled: boolean;
  portalEnabled: boolean;
  positionOpen: boolean;
  onChange: (enabled: boolean) => void;
}

// HR switch for the public /apply form of one position.
export default function PublicApplyToggle({ positionId, enabled, portalEnabled, positionOpen, onChange }: PublicApplyToggleProps) {
  const { t } = useI18n();
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
          {enabled && portalEnabled && positionOpen && (
            <Typography variant="body2" color="text.secondary">
              {t('Ứng viên có thể nộp CV tại')}{' '}
              <MuiLink href="/apply" target="_blank" rel="noopener">/apply</MuiLink>
            </Typography>
          )}
          {enabled && !positionOpen && (
            <Alert severity="info" sx={{ mt: 1 }}>{t('Vị trí không ở trạng thái Đang mở nên chưa hiện trên trang /apply.')}</Alert>
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
