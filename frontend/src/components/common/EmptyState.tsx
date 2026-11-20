'use client';

import * as React from 'react';
import { Box, Card, CardContent, Typography } from '@mui/material';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Card
      variant="outlined"
      sx={{
        borderStyle: 'dashed',
        borderColor: '#CBD5E1',
        backgroundColor: '#FFFFFF',
        boxShadow: 'none',
      }}
    >
      <CardContent sx={{ textAlign: 'center', py: 6, px: 3 }}>
        <Box
          sx={{
            width: 52,
            height: 52,
            borderRadius: '12px',
            backgroundColor: '#F1F5F9',
            color: '#64748B',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 1.75,
          }}
        >
          <InboxOutlinedIcon sx={{ fontSize: 26 }} aria-hidden />
        </Box>
        <Typography variant="h3" sx={{ fontSize: 16, color: '#0F172A' }}>{title}</Typography>
        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, maxWidth: 520, mx: 'auto' }}>
            {description}
          </Typography>
        )}
        {action && <Box sx={{ mt: 2.5 }}>{action}</Box>}
      </CardContent>
    </Card>
  );
}
