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
    <Card variant="outlined" sx={{ borderStyle: 'dashed', backgroundColor: '#FCFDFF' }}>
      <CardContent sx={{ textAlign: 'center', py: 5, px: 3 }}>
        <InboxOutlinedIcon sx={{ fontSize: 42, color: '#98A2B3', mb: 1.5 }} aria-hidden />
        <Typography variant="h3" sx={{ fontSize: 17, color: '#0A2B57' }}>{title}</Typography>
        {description && <Typography variant="body2" color="text.secondary" sx={{ mt: 1, maxWidth: 560, mx: 'auto' }}>{description}</Typography>}
        {action && <Box sx={{ mt: 2.5 }}>{action}</Box>}
      </CardContent>
    </Card>
  );
}
