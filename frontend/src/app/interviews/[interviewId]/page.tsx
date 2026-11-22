'use client';

/**
 * Chấm điểm cho một buổi phỏng vấn.
 *
 * Vì sao có màn này: ở B2, HR bấm "Tạo phiếu chấm điểm" rồi… hết đường. Phiếu
 * được tạo trong DB nhưng không màn hình nào mở được ra, vì panel chấm duy nhất
 * của app (`ScorecardPanel`) chỉ biết nguồn là *share*, còn buổi phỏng vấn không
 * có share nào. Người phỏng vấn nhận việc qua lời nói, và chỉ chấm được bằng
 * cách gọi API trực tiếp.
 *
 * Màn này nối đúng chỗ đứt đó: dùng lại chính `ScorecardPanel` với nguồn
 * `interview`, để hai đường chấm không trôi khỏi nhau (cùng ô nhập, cùng quy tắc
 * nộp, cùng nháp trên trình duyệt, cùng cách xử lý mất quyền).
 */

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Alert, Breadcrumbs, CircularProgress, Box, Chip, Stack, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { interviewsApi } from '@/lib/api';
import ScorecardPanel from '@/components/shortlist/ScorecardPanel';
import { formatVietnamTime } from '@/components/positions/InterviewPanel';
import { purgeShareDrafts } from '@/lib/localDrafts';

type Participant = { user_id: string; participant_role: string; display_name?: string | null; email?: string | null };
type Interview = {
  interview_id: string; application_id: string; position_id: string;
  position_code?: string | null; position_title?: string | null;
  candidate_name?: string | null; round_number: number; status: string;
  starts_at: string; ends_at: string; location_kind: string; location_text?: string | null;
  participants?: Participant[];
};

const STATUS_LABEL: Record<string, string> = {
  SCHEDULED: 'Đã hẹn', DONE: 'Đã diễn ra', CANCELLED: 'Đã huỷ', NO_SHOW: 'Ứng viên không đến',
};

export default function InterviewScorecardPage() {
  const { t } = useI18n();
  const interviewId = String(useParams().interviewId);
  const [interview, setInterview] = useState<Interview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // Cùng quy ước với trang share: mất quyền thì xoá luôn nháp đã gõ trên máy
  // này. Không xoá thì người đã bị thu quyền vẫn đọc lại được nội dung đánh giá
  // ứng viên từ localStorage.
  const accessLost = useCallback(() => {
    purgeShareDrafts(`interview:${interviewId}`);
    setInterview(null);
    setLoading(false);
    setError('Không có quyền xem buổi phỏng vấn này, hoặc buổi đã bị xoá.');
  }, [interviewId]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    interviewsApi.get(interviewId)
      .then(res => { if (live) setInterview(res.data as Interview); })
      .catch((err: any) => {
        if (!live) return;
        if ([403, 404].includes(err.response?.status)) accessLost();
        else setError(t('Không tải được buổi phỏng vấn.'));
      })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [interviewId, accessLost, t]);

  if (loading) return <Box sx={{ p: 3 }}><CircularProgress size={24} /></Box>;
  if (error) return <Box sx={{ p: 3 }}><Alert severity="error">{t(error)}</Alert></Box>;
  if (!interview) return null;

  const interviewers = (interview.participants || []).filter(p => p.participant_role === 'INTERVIEWER');

  return (
    <Box sx={{ p: 3, maxWidth: 980 }}>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link href="/interviews">{t('Lịch phỏng vấn')}</Link>
        <Typography color="text.secondary">{t('Vòng')} {interview.round_number}</Typography>
      </Breadcrumbs>

      <Typography variant="h6" fontWeight={700}>
        {interview.candidate_name || t('Ứng viên')} · {t('Vòng')} {interview.round_number}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {interview.position_code} {interview.position_title ? `· ${interview.position_title}` : ''}
      </Typography>

      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', rowGap: 1 }}>
        <Chip size="small" label={formatVietnamTime(interview.starts_at)} />
        <Chip size="small" variant="outlined" label={t(STATUS_LABEL[interview.status] || interview.status)} />
        {/* Nói rõ ai có phiếu: người phỏng vấn mở màn này cần biết mình có trong
            danh sách hay không trước khi điền, thay vì điền xong mới bị từ chối. */}
        {interviewers.length > 0 && (
          <Chip size="small" variant="outlined"
            label={`${t('Người phỏng vấn')}: ${interviewers.map(p => p.display_name || p.email || t('Không rõ')).join(', ')}`} />
        )}
      </Stack>

      {interview.status === 'CANCELLED' && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t('Buổi này đã bị huỷ nên không chấm điểm được. Nếu cần phỏng vấn lại, tạo buổi mới cùng vòng trong hồ sơ ứng viên.')}
        </Alert>
      )}

      {/* Vẫn render panel khi buổi đã huỷ: nó hiện phiếu đã nộp ở chế độ chỉ đọc.
          Ẩn đi thì HR mất luôn khả năng xem lại đánh giá của buổi đã huỷ. */}
      <ScorecardPanel
        source={{ kind: 'interview', interviewId }}
        candidates={[{ application_id: interview.application_id, candidate_name: interview.candidate_name || undefined }]}
        onAccessLost={accessLost}
      />
    </Box>
  );
}
