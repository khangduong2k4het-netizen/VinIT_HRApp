'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export default function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 3 }}>
      <Box sx={{ minWidth: 0 }}>
        {eyebrow && <Typography variant="overline" color="secondary.main">{eyebrow}</Typography>}
        <Typography component="h1" variant="h1" sx={{ color: '#0A2B57', mt: eyebrow ? 0.5 : 0, overflowWrap: 'anywhere' }}>{title}</Typography>
        {description && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{description}</Typography>}
      </Box>
      {actions && <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>{actions}</Box>}
    </Box>
  );
}
