'use client';

import * as React from 'react';
import { Box, Button } from '@mui/material';
import { useI18n } from './I18nProvider';

export default function LanguageSwitcher({ light = false }: { light?: boolean }) {
  const { locale, setLocale, t } = useI18n();
  return (
    <Box
      role="group"
      aria-label={t('Chọn ngôn ngữ')}
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        p: '2px',
        borderRadius: '8px',
        flexShrink: 0,
        backgroundColor: light ? 'rgba(255,255,255,0.14)' : '#F1F5F9',
        border: light ? '1px solid rgba(255,255,255,0.22)' : '1px solid #E2E8F0',
      }}
    >
      {(['vi', 'en'] as const).map(code => {
        const active = locale === code;
        return (
          <Button
            key={code}
            size="small"
            aria-label={code === 'vi' ? 'Tiếng Việt' : 'English'}
            aria-pressed={active}
            onClick={() => setLocale(code)}
            sx={{
              minWidth: 32,
              px: 0.9,
              py: 0.35,
              fontSize: '11.5px',
              lineHeight: 1.2,
              borderRadius: '6px',
              fontWeight: active ? 700 : 500,
              color: light
                ? (active ? '#0A2B57' : 'rgba(255,255,255,0.85)')
                : (active ? '#0A2B57' : '#64748B'),
              backgroundColor: active ? '#FFFFFF' : 'transparent',
              boxShadow: active ? '0 1px 2px rgba(15,23,42,0.08)' : 'none',
              '&:hover': {
                backgroundColor: active
                  ? '#FFFFFF'
                  : (light ? 'rgba(255,255,255,0.12)' : 'rgba(15,23,42,0.04)'),
              },
            }}
          >
            {code.toUpperCase()}
          </Button>
        );
      })}
    </Box>
  );
}
