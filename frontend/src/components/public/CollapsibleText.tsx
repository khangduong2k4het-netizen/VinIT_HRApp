'use client';

import * as React from 'react';
import { useEffect, useRef, useState } from 'react';
import { Box, Button } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';

// Long text (a job description) shown clamped with a fade and a "show more" button.
// `enabled` lets the caller turn the clamp off, for example on wide screens where
// the application form sits next to the text instead of far below it.
export default function CollapsibleText({
  children, collapsedHeight = 360, enabled = true,
}: { children: React.ReactNode; collapsedHeight?: number; enabled?: boolean }) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (element) setOverflowing(element.scrollHeight > collapsedHeight + 24);
  }, [children, collapsedHeight, enabled]);
  const clamped = enabled && !expanded;
  return (
    <Box>
      <Box ref={ref} sx={{ position: 'relative', maxHeight: clamped ? collapsedHeight : 'none', overflow: clamped ? 'hidden' : 'visible' }}>
        {children}
        {clamped && overflowing && (
          <Box
            aria-hidden
            sx={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 88, pointerEvents: 'none',
              background: 'linear-gradient(to bottom, rgba(255,255,255,0), #FFFFFF)' }}
          />
        )}
      </Box>
      {enabled && overflowing && (
        <Button size="small" onClick={() => setExpanded(value => !value)} aria-expanded={expanded} sx={{ mt: 1, minHeight: 40 }}>
          {expanded ? t('Thu gọn') : t('Xem thêm')}
        </Button>
      )}
    </Box>
  );
}
