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
        top: { xs: 72, md: 76 },
        zIndex: 5,
        backgroundColor: 'rgba(255,255,255,.96)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #E4EAF2',
        borderRadius: 2,
        boxShadow: '0 6px 20px rgba(10,43,87,.08)',
        px: 2,
        // Ở màn hẹp đã gọn còn hai hàng, nên bớt luôn phần đệm dọc: 10px → 6px
        // mỗi bên (thanh 118 → 112px ở 390px). Từ 600px trở lên giữ nguyên.
        py: { xs: 0.75, sm: 1.25 },
        mb: 2,
      }}
    >
      {children}
    </Box>
  );
}
