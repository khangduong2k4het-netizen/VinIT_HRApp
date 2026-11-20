'use client';

import * as React from 'react';
import { Box } from '@mui/material';

interface StickyActionBarProps {
  children: React.ReactNode;
}

export default function StickyActionBar({ children }: StickyActionBarProps) {
  return (
    <Box
      sx={{
        position: 'sticky',
        top: { xs: 64, md: 68 },
        zIndex: 5,
        backgroundColor: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(10px)',
        border: '1px solid #E5EAF0',
        borderRadius: '12px',
        boxShadow: '0 6px 20px rgba(15, 23, 42, 0.06)',
        px: 2,
        py: 1.25,
        mb: 2.5,
      }}
    >
      {children}
    </Box>
  );
}
