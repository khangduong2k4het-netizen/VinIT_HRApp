'use client';

import * as React from 'react';
import { useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, CircularProgress, Stack, TextField, Typography,
} from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { adminApi } from '@/lib/api';

/**
 * HR thresholds that used to be constants in the backend.
 *
 * The page deliberately shows the allowed range next to the field: a number that
 * only fails on save teaches nothing. Saving is per row so a mistake in one
 * setting cannot block the others.
 */
interface Setting {
  key: string;
  value: number;
  default: number;
  min: number;
  max: number;
  label: string;
  description: string;
}

export default function HrSettings() {
  const { t } = useI18n();
  const [settings, setSettings] = useState<Setting[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = React.useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const response = await adminApi.getSettings();
      setSettings(response.data.settings);
      setDrafts(Object.fromEntries(response.data.settings.map((s: Setting) => [s.key, String(s.value)])));
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không tải được cài đặt.'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  React.useEffect(() => { load(); }, [load]);

  const save = async (setting: Setting) => {
    const raw = (drafts[setting.key] ?? '').trim();
    // Catch the obvious cases before a round trip, and say why.
    if (!/^\d+$/.test(raw)) {
      setError(t('“{0}” phải là một số nguyên.', setting.label));
      return;
    }
    const value = Number(raw);
    if (value < setting.min || value > setting.max) {
      setError(t('“{0}” phải nằm trong khoảng {1}–{2} ngày.', setting.label, setting.min, setting.max));
      return;
    }
    try {
      setSavingKey(setting.key); setError(null); setSuccess(null);
      await adminApi.updateSetting(setting.key, value);
      await load();
      setSuccess(t('Đã lưu “{0}”: {1} ngày. Dashboard và danh sách ứng viên dùng con số này ngay lần tải sau.', setting.label, value));
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không lưu được cài đặt.'));
    } finally {
      setSavingKey(null);
    }
  };

  if (loading && !settings) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" /></Box>;
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}
      <Alert severity="info" sx={{ mb: 3 }}>
        {t('Đây là những con số nghiệp vụ HR tự đặt, không phải hằng số kỹ thuật. Thay đổi có hiệu lực ngay và được ghi vào nhật ký kiểm toán.')}
      </Alert>
      <Stack spacing={2} data-testid="hr-settings">
        {(settings || []).map(setting => {
          const draft = drafts[setting.key] ?? '';
          const dirty = draft !== String(setting.value);
          const invalid = !/^\d+$/.test(draft.trim()) || Number(draft) < setting.min || Number(draft) > setting.max;
          return (
            <Card variant="outlined" key={setting.key} sx={{ borderColor: '#E4EAF2' }}>
              <CardContent sx={{ display: 'flex', gap: 3, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <Box sx={{ flex: '1 1 320px', minWidth: 260 }}>
                  <Typography variant="subtitle1" fontWeight={700} color="#0A2B57">{t(setting.label)}</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{t(setting.description)}</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                    {t('Cho phép {0}–{1} ngày · mặc định {2} ngày', setting.min, setting.max, setting.default)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                  <TextField
                    type="number"
                    size="small"
                    label={t('Số ngày')}
                    value={draft}
                    onChange={event => setDrafts({ ...drafts, [setting.key]: event.target.value })}
                    error={dirty && invalid}
                    helperText={dirty && invalid ? t('Ngoài khoảng cho phép') : ' '}
                    inputProps={{ min: setting.min, max: setting.max, step: 1, 'aria-label': `${t(setting.label)} — ${t('Số ngày')}` }}
                    sx={{ width: 140 }}
                  />
                  <Button
                    variant="contained"
                    color="secondary"
                    onClick={() => save(setting)}
                    disabled={!dirty || invalid || savingKey !== null}
                    sx={{ mt: 0.5 }}
                  >{savingKey === setting.key ? t('Đang lưu...') : t('Lưu')}</Button>
                </Box>
              </CardContent>
            </Card>
          );
        })}
      </Stack>
    </Box>
  );
}
