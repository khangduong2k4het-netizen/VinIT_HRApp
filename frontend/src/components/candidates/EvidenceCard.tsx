'use client';

import * as React from 'react';
import { Alert, Box, Card, CardContent, Chip, Paper, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { CriterionResult } from '@/types';

const outcomeStyles: Record<string, { borderColor: string; label: string; color: string }> = {
  STRONG_MATCH: { borderColor: '#067647', label: 'Đáp ứng tốt', color: '#067647' },
  MATCH: { borderColor: '#0A2B57', label: 'Đáp ứng', color: '#0A2B57' },
  UNCLEAR: { borderColor: '#B54708', label: 'Chưa rõ', color: '#B54708' },
  NO_MATCH: { borderColor: '#C72127', label: 'Chưa đáp ứng', color: '#C72127' },
};

interface EvidenceCardProps {
  result: CriterionResult;
  isPdf: boolean;
  hasCv: boolean;
  selected: boolean;
  onJumpToPage: (page: number, criterionId: string) => void;
}

export default function EvidenceCard({ result, isPdf, hasCv, selected, onJumpToPage }: EvidenceCardProps) {
  const { t } = useI18n();
  const style = outcomeStyles[result.outcome] || outcomeStyles.UNCLEAR;
  const citation = result.evidence?.[0];
  const verified = citation?.verification_status === 'VERIFIED' || citation?.verification_status === 'MANUAL_FIX';
  const page = citation?.page_number || result.page_number;
  const quote = result.verbatim_quote || citation?.verbatim_quote;
  const canJump = Boolean(verified && page && isPdf && hasCv);

  return (
    <Card
      className={`evidence-card ${result.outcome.toLowerCase().replace('_', '-')}`}
      sx={{
        borderLeft: `4px solid ${style.borderColor}`,
        borderRadius: '0 8px 8px 0',
        boxShadow: selected ? '0 0 0 2px rgba(37,153,220,.35), 0 4px 14px rgba(10,43,87,.10)' : '0 1px 3px rgba(0,0,0,0.05)',
      }}
    >
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1, gap: 1 }}>
          <Box>
            <Chip label={t(style.label)} size="small" sx={{ backgroundColor: `${style.borderColor}15`, color: style.color, fontWeight: 700, fontSize: 11, height: 22, mr: 1, mb: 0.5 }} />
            <Chip label={result.category === 'MUST_HAVE' ? t("Bắt buộc") : t("Ưu tiên")} size="small" sx={{ backgroundColor: result.category === 'MUST_HAVE' ? '#FDF2F2' : '#E8F1FC', color: result.category === 'MUST_HAVE' ? '#941616' : '#0A2B57', fontWeight: 600, fontSize: 10, height: 22, mr: 1 }} />
            {result.decision_source && (
              <Chip
                label={`${t(result.decision_source === 'RULE' ? "Theo quy tắc xác định" : result.decision_source === 'HYBRID' ? "Quy tắc + AI" : "AI đối chiếu")}${result.evidence_strength != null ? ` · ${Math.round(result.evidence_strength * 100)}%` : ''}`}
                size="small"
                sx={{ backgroundColor: result.decision_source === 'RULE' ? '#ECFDF3' : result.decision_source === 'HYBRID' ? '#F4EBFF' : '#F2F4F7', color: result.decision_source === 'RULE' ? '#067647' : result.decision_source === 'HYBRID' ? '#6941C6' : '#344054', fontWeight: 600, fontSize: 10, height: 22 }}
              />
            )}
          </Box>
          {result.score !== null && <Typography variant="h6" sx={{ fontSize: 16, fontWeight: 'bold', color: style.color }}>{result.score}%</Typography>}
        </Box>

        <Typography variant="body1" sx={{ fontWeight: 600, fontSize: 14, mb: 0.5 }}>{result.criterion_name}</Typography>
        {result.reasoning && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{result.reasoning}</Typography>}

        {quote ? (
          <Paper
            elevation={0}
            sx={{ backgroundColor: selected ? '#EFF8FF' : '#F8FAFC', borderLeft: '2px solid #E2E8F0', p: 1.5, borderRadius: 1, mt: 1, cursor: canJump ? 'pointer' : 'default', '&:hover': canJump ? { backgroundColor: '#F1F5F9' } : undefined }}
            role={canJump ? 'button' : undefined}
            tabIndex={canJump ? 0 : undefined}
            aria-label={canJump ? t("Mở trang {0} trong CV để kiểm tra bằng chứng", page || '') : undefined}
            onClick={() => { if (canJump && page) onJumpToPage(page, result.criterion_id); }}
            onKeyDown={event => { if (canJump && page && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onJumpToPage(page, result.criterion_id); } }}
          >
            <Typography variant="body2" sx={{ fontStyle: 'italic', color: '#112434', fontSize: 13, lineHeight: 1.6 }}>&ldquo;{quote}&rdquo;</Typography>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
              <Chip label={!verified ? t("Trích dẫn chưa xác minh") : (isPdf && page ? t("Trang {0} · Đã xác minh", page) : t("Đoạn trích đã xác minh"))} size="small" sx={{ backgroundColor: verified ? '#0A2B57' : '#B54708', color: 'white', fontWeight: 700, fontSize: 10, height: 20 }} />
            </Box>
          </Paper>
        ) : (
          <Paper elevation={0} sx={{ backgroundColor: '#FFFAEB', p: 1.5, borderRadius: 1, mt: 1 }}>
            <Typography variant="body2" color="#B54708">{t("Chưa có bằng chứng được trích xuất cho tiêu chí này.")}</Typography>
          </Paper>
        )}

        {result.outcome === 'UNCLEAR' && <Alert severity="warning" icon={false} sx={{ mt: 2, py: 0, fontSize: 12 }}>{t("Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV để xác minh.")}</Alert>}
      </CardContent>
    </Card>
  );
}
