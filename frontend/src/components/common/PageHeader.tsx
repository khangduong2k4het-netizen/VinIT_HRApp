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
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: 2,
        flexWrap: 'wrap',
        mb: 3,
        pb: 2,
        borderBottom: '1px solid #E5EAF0',
      }}
    >
      <Box sx={{ minWidth: 0 }}>
        {eyebrow && (
          <Typography
            variant="overline"
            sx={{
              color: '#C72127',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.75,
              mb: 0.5,
            }}
          >
            {eyebrow}
          </Typography>
        )}
        <Typography
          component="h1"
          variant="h1"
          sx={{ color: '#0F172A', overflowWrap: 'anywhere' }}
        >
          {title}
        </Typography>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 780 }}>
            {description}
          </Typography>
        )}
      </Box>
      {actions && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', pt: { xs: 0.5, sm: 0.25 } }}>
          {actions}
        </Box>
      )}
    </Box>
  );
}
