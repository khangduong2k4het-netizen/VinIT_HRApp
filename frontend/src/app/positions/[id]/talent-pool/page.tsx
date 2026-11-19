'use client';

// P3-1: scan the Talent Pool for one position (opened from the position page).
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Alert, Box, Button, Card, CardContent, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { positionsApi } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';
import ScanPanel from '@/components/talent-pool/ScanPanel';

export default function PositionTalentPoolPage() {
  const { t } = useI18n();
  const positionId = useParams().id as string;
  const [title, setTitle] = useState('');
  useEffect(() => {
    positionsApi.getById(positionId).then(res => setTitle(`${res.data.position_code} · ${res.data.title}`)).catch(() => undefined);
  }, [positionId]);
  return <Box>
    <Button component={Link} href={`/positions/${positionId}`} startIcon={<ArrowBackIcon />} sx={{ mb: 1 }}>{t('Quay lại vị trí')}</Button>
    <Typography variant="h2" sx={{ fontSize: 22, color: '#0A2B57', mb: 0.5 }}>{t('Quét Talent Pool')}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{title}</Typography>
    <Alert severity="info" sx={{ mb: 2 }}>
      {t('Chỉ gồm hồ sơ HR đã đưa vào pool, ứng viên đã đồng ý cho dùng ở vị trí khác và chưa rút, còn trong hạn 5 năm và không chờ xóa. Hệ thống chỉ gợi ý xếp hạng; HR quyết định liên hệ.')}
    </Alert>
    <Card><CardContent><ScanPanel positionId={positionId} /></CardContent></Card>
  </Box>;
}
