'use client';

import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Alert, Box, Button, Card, CardContent, Container, Stack, TextField, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { withdrawTalentPool } from '@/lib/publicApply';

export default function WithdrawPage() {
  const { t } = useI18n();
  const [token, setToken] = useState('');
  const [state, setState] = useState<'idle' | 'invalid' | 'done' | 'error'>('idle');
  const [busy, setBusy] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (!/^[0-9a-fA-F]{64}$/.test(token.trim())) { setState('invalid'); return; }
    setBusy(true);
    setState((await withdrawTalentPool(token)) ? 'done' : 'error');
    setBusy(false);
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#F8FAFC' }}>
      <Box component="header" sx={{ bgcolor: 'primary.main', color: '#fff', py: 1.5 }}>
        <Container maxWidth="sm" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ bgcolor: '#fff', borderRadius: 1, px: 1, py: 0.5, display: 'flex' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/vinuni-logo.png" alt="VinUniversity" height={28} />
            </Box>
            <Typography component="h1" variant="h6" sx={{ fontWeight: 700 }}>{t('Rút lại đồng ý Talent Pool')}</Typography>
          </Stack>
          <LanguageSwitcher light />
        </Container>
      </Box>
      <Container maxWidth="sm" sx={{ py: { xs: 3, md: 5 } }}>
        <Button component={Link} href="/apply" size="small" sx={{ mb: 2 }}>{t('← Quay lại danh sách')}</Button>
        {state === 'done' ? (
          <Alert severity="success" role="status">{t('Nếu mã hợp lệ, lựa chọn Talent Pool đã được rút.')}</Alert>
        ) : (
          <Card component="form" onSubmit={submit} noValidate>
            <CardContent>
              <Stack spacing={2}>
                <TextField label={t('Mã rút lại đồng ý')} value={token} onChange={e => { setToken(e.target.value); setState('idle'); }}
                  error={state === 'invalid'} helperText={state === 'invalid' ? t('Mã gồm 64 ký tự (0-9, a-f).') : undefined} fullWidth />
                {state === 'error' && <Alert severity="error">{t('Không thể kết nối. Vui lòng thử lại.')}</Alert>}
                <Button type="submit" variant="contained" disabled={busy}>{t('Rút lại đồng ý')}</Button>
              </Stack>
            </CardContent>
          </Card>
        )}
      </Container>
    </Box>
  );
}
