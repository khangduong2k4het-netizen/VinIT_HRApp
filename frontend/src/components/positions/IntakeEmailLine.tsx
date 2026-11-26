'use client';

// F3.03 email channel: the address candidates can send a CV to for this position.
import * as React from 'react';
import { useEffect, useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import AlternateEmailIcon from '@mui/icons-material/AlternateEmail';
import { mailboxApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

export default function IntakeEmailLine({ positionCode }: { positionCode: string }) {
  const { t } = useI18n();
  const [address, setAddress] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    mailboxApi.intakeAddress(positionCode).then(r => { if (active) setAddress(r.data.address); }).catch(() => { /* no mailbox */ });
    return () => { active = false; };
  }, [positionCode]);

  if (!address) return null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(address); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* ignore */ }
  };
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <AlternateEmailIcon fontSize="small" color="action" />
      <Typography variant="body2">{t('Email nhận CV cho vị trí này:')}</Typography>
      <Typography variant="body2" component="code" className="mono-code" sx={{ fontWeight: 600, color: 'primary.main', wordBreak: 'break-all' }}>
        {address}
      </Typography>
      <Button size="small" variant="text" onClick={copy}>{copied ? t('Đã sao chép') : t('Sao chép')}</Button>
      <Typography variant="caption" color="text.secondary">{t('Dán vào tin tuyển dụng; CV gửi tới địa chỉ này tự vào vị trí.')}</Typography>
    </Box>
  );
}
