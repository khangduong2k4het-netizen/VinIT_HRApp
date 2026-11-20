'use client';

import { Box } from '@mui/material';
import Chip from '@mui/material/Chip';

export type BadgeType =
  | 'file-completed'
  | 'file-processing'
  | 'file-review'
  | 'file-error'
  | 'match-meets'
  | 'match-verify'
  | 'match-mismatch'
  | 'app-new'
  | 'app-review'
  | 'app-shortlist'
  | 'app-rejected'
  | 'position-open'
  | 'position-paused'
  | 'position-closed'
  | 'criteria-draft'
  | 'criteria-approved';

interface StatusBadgeProps {
  type: BadgeType;
  label: string;
}

const colorMap: Record<BadgeType, { bg: string; text: string; border: string; dot: string }> = {
  'file-completed': { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6', dot: '#12B76A' },
  'file-processing': { bg: '#EFF8FF', text: '#134D8B', border: '#B2DDFF', dot: '#2E90FA' },
  'file-review': { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89', dot: '#F79009' },
  'file-error': { bg: '#FEF3F2', text: '#B42318', border: '#FECDCA', dot: '#F04438' },
  'match-meets': { bg: '#EEF4FC', text: '#0A2B57', border: '#C7DDF7', dot: '#0A2B57' },
  'match-verify': { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89', dot: '#F79009' },
  'match-mismatch': { bg: '#FEF2F2', text: '#941616', border: '#FECACA', dot: '#C72127' },
  'app-new': { bg: '#F1F5F9', text: '#475569', border: '#E2E8F0', dot: '#64748B' },
  'app-review': { bg: '#EFF8FF', text: '#175CD3', border: '#B2DDFF', dot: '#2E90FA' },
  'app-shortlist': { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6', dot: '#12B76A' },
  'app-rejected': { bg: '#FEF3F2', text: '#B42318', border: '#FECDCA', dot: '#F04438' },
  'position-open': { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6', dot: '#12B76A' },
  'position-paused': { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89', dot: '#F79009' },
  'position-closed': { bg: '#F1F5F9', text: '#475569', border: '#E2E8F0', dot: '#64748B' },
  'criteria-draft': { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89', dot: '#F79009' },
  'criteria-approved': { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6', dot: '#12B76A' },
};

export default function StatusBadge({ type, label }: StatusBadgeProps) {
  const colors = colorMap[type];
  return (
    <Chip
      size="small"
      label={
        <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
          <Box
            component="span"
            aria-hidden
            sx={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: colors.dot, flexShrink: 0 }}
          />
          {label}
        </Box>
      }
      sx={{
        backgroundColor: colors.bg,
        color: colors.text,
        border: `1px solid ${colors.border}`,
        fontWeight: 600,
        fontSize: 11.5,
        letterSpacing: '0.01em',
        borderRadius: '7px',
        height: 24,
        '& .MuiChip-label': { px: 1 },
      }}
    />
  );
}
