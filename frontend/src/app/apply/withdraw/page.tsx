'use client';

import * as React from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { Alert, Box, Button, Card, CardContent, Container, Divider, Stack, TextField, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
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
    <Box sx={{ minHeight: '100vh', bgcolor: '#F6F8FB' }}>
      <Box
        component="header"
        sx={{
          bgcolor: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(10px)',
          borderBottom: '1px solid #E5EAF0',
        }}
      >
        <Container maxWidth="sm" sx={{ height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/vinuni-logo.png" alt="VinUniversity" height={28} style={{ display: 'block' }} />
            <Divider orientation="vertical" flexItem sx={{ my: 1.5 }} />
            <Typography component="h1" sx={{ fontWeight: 700, fontSize: 14, color: '#0A2B57' }}>
              {t('Rút lại đồng ý Talent Pool')}
            </Typography>
          </Stack>
          <LanguageSwitcher />
        </Container>
      </Box>
      <Container maxWidth="sm" sx={{ py: { xs: 3, md: 5 } }}>
        <Button component={Link} href="/apply" size="small" startIcon={<ArrowBackIcon fontSize="small" />} sx={{ mb: 2, color: '#475569' }}>
          {t('Quay lại danh sách vị trí')}
        </Button>
        {state === 'done' ? (
          <Alert severity="success" role="status">{t('Nếu mã hợp lệ, lựa chọn Talent Pool đã được rút.')}</Alert>
        ) : (
          <Card component="form" onSubmit={submit} noValidate sx={{ overflow: 'hidden' }}>
            <Box sx={{ height: 3.5, bgcolor: '#0A2B57' }} />
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h3" sx={{ color: '#0F172A', mb: 0.75 }}>{t('Rút lại đồng ý Talent Pool')}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
                {t('Nhập mã 64 ký tự bạn đã nhận sau khi nộp hồ sơ để ngừng sử dụng hồ sơ cho các vị trí tuyển dụng khác.')}
              </Typography>
              <Stack spacing={2}>
                <TextField
                  label={t('Mã rút lại đồng ý')}
                  value={token}
                  onChange={e => { setToken(e.target.value); setState('idle'); }}
                  error={state === 'invalid'}
                  helperText={state === 'invalid' ? t('Mã gồm 64 ký tự (0-9, a-f).') : undefined}
                  inputProps={{ className: 'mono-code' }}
                  fullWidth
                />
                {state === 'error' && <Alert severity="error">{t('Không thể kết nối. Vui lòng thử lại.')}</Alert>}
                <Button type="submit" variant="contained" color="secondary" disabled={busy} sx={{ alignSelf: 'flex-start' }}>
                  {t('Rút lại đồng ý')}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        )}
      </Container>
    </Box>
  );
}
