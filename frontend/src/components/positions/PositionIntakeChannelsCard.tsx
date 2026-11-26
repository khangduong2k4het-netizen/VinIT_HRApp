'use client';

// Grouped card for HR intake channels on a position: public /apply portal + Gmail intake address.
import * as React from 'react';
import { useState } from 'react';
import { Box, Button, Card, CardContent, FormControlLabel, Stack, Switch, Typography } from '@mui/material';
import LinkIcon from '@mui/icons-material/Link';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import IntakeEmailLine from './IntakeEmailLine';
import { useI18n } from '@/i18n/I18nProvider';

interface Props {
  positionCode?: string | null;
  positionStatus: string;
  approvedCriteria: boolean;
  publicApplyEnabled: boolean;
  publicApplyBusy: boolean;
  onTogglePublicApply: (event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => void;
}

export default function PositionIntakeChannelsCard({
  positionCode,
  positionStatus,
  approvedCriteria,
  publicApplyEnabled,
  publicApplyBusy,
  onTogglePublicApply,
}: Props) {
  const { t } = useI18n();
  const [copiedLink, setCopiedLink] = useState(false);

  const canAcceptPublic = positionStatus === 'OPEN' && approvedCriteria;
  const copyApplyLink = async () => {
    if (!positionCode || typeof window === 'undefined') return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/apply?position=${encodeURIComponent(positionCode)}`);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch { /* ignore */ }
  };

  return (
    <Card variant="outlined" sx={{ mb: 2.5 }}>
      <CardContent sx={{ py: 1.75, '&:last-child': { pb: 1.75 } }}>
        <Stack spacing={1.25}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }} justifyContent="space-between">
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <PublicOutlinedIcon fontSize="small" color="action" />
              <FormControlLabel
                sx={{ mr: 0 }}
                control={<Switch size="small" checked={publicApplyEnabled} disabled={publicApplyBusy} onChange={onTogglePublicApply} />}
                label={<Typography variant="body2" fontWeight={600}>{t("Nhận hồ sơ qua cổng ứng tuyển công khai (/apply)")}</Typography>}
              />
            </Stack>
            {publicApplyEnabled && positionCode && (
              <Button size="small" variant="outlined" startIcon={<LinkIcon fontSize="small" />} onClick={copyApplyLink}>
                {copiedLink ? t('Đã sao chép') : t('Sao chép link /apply')}
              </Button>
            )}
          </Stack>
          <Typography variant="caption" color={publicApplyEnabled && !canAcceptPublic ? 'warning.main' : 'text.secondary'}>
            {publicApplyEnabled && !canAcceptPublic
              ? t("Đang bật nhưng chưa hiện trên cổng: vị trí phải đang mở và có bộ tiêu chí đã duyệt.")
              : t("Ứng viên tự nộp CV, bắt buộc đồng ý cho sử dụng thông tin; CV được chấm như hồ sơ HR tải lên.")}
          </Typography>
          {positionCode && (
            <Box sx={{ pt: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
              <IntakeEmailLine positionCode={positionCode} />
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
