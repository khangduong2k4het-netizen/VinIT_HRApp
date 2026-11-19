'use client';

import * as React from 'react';
import { Alert, Box, Button, Card, CardContent, Chip, Paper, Stack, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useI18n } from '@/i18n/I18nProvider';
import type { CriterionResult } from '@/types';

const outcomeStyles: Record<string, { borderColor: string; bg: string; label: string; color: string; dot: string }> = {
  STRONG_MATCH: { borderColor: '#067647', bg: '#ECFDF3', label: 'Đáp ứng tốt', color: '#067647', dot: '#12B76A' },
  MATCH: { borderColor: '#0A2B57', bg: '#EEF4FC', label: 'Đáp ứng', color: '#0A2B57', dot: '#0A2B57' },
  UNCLEAR: { borderColor: '#D97706', bg: '#FFFAEB', label: 'Chưa rõ', color: '#B54708', dot: '#F79009' },
  NO_MATCH: { borderColor: '#C72127', bg: '#FEF2F2', label: 'Chưa đáp ứng', color: '#941616', dot: '#C72127' },
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

  const sourceLabel = result.decision_source === 'RULE'
    ? t('Theo quy tắc xác định')
    : result.decision_source === 'HYBRID'
      ? t('Quy tắc + AI')
      : result.decision_source
        ? t('AI đối chiếu')
        : '';

  return (
    <Card
      className={`evidence-card ${result.outcome.toLowerCase().replace('_', '-')}`}
      sx={{
        borderLeft: `3.5px solid ${style.borderColor}`,
        borderRadius: '10px',
        boxShadow: selected
          ? '0 0 0 2px rgba(37, 153, 220, 0.35), 0 6px 18px rgba(10, 43, 87, 0.08)'
          : '0 1px 2px rgba(15, 23, 42, 0.04)',
      }}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        {/* Clean 1-line metadata + mono score */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              label={
                <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.6 }}>
                  <Box component="span" aria-hidden sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: style.dot }} />
                  {t(style.label)}
                </Box>
              }
              sx={{
                backgroundColor: style.bg,
                color: style.color,
                border: `1px solid ${style.borderColor}30`,
                fontWeight: 600,
                fontSize: 11.5,
                height: 23,
              }}
            />
            <Typography
              variant="caption"
              sx={{
                fontWeight: 600,
                fontSize: 11,
                color: result.category === 'MUST_HAVE' ? '#941616' : '#475569',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              {result.category === 'MUST_HAVE' ? t('Bắt buộc') : t('Ưu tiên')}
            </Typography>
            {sourceLabel && (
              <Typography variant="caption" color="text.secondary" className="tabular-nums">
                · {sourceLabel}{result.evidence_strength != null ? ` (${Math.round(result.evidence_strength * 100)}%)` : ''}
              </Typography>
            )}
          </Stack>
          {result.score !== null && (
            <Typography
              className="mono-code"
              sx={{ fontSize: 15, fontWeight: 700, color: style.color, flexShrink: 0 }}
            >
              {result.score}%
            </Typography>
          )}
        </Box>

        <Typography variant="body1" sx={{ fontWeight: 600, fontSize: 14, color: '#0F172A', mb: 0.5 }}>
          {result.criterion_name}
        </Typography>
        {result.reasoning && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, fontSize: 13 }}>
            {result.reasoning}
          </Typography>
        )}

        {quote ? (
          <Paper
            elevation={0}
            sx={{
              backgroundColor: selected ? '#EEF6FE' : '#F8FAFC',
              border: '1px solid',
              borderColor: selected ? '#B2DDFF' : '#E5EAF0',
              borderLeft: '3px solid',
              borderLeftColor: selected ? '#2599DC' : '#CBD5E1',
              p: 1.5,
              borderRadius: '8px',
              mt: 1,
              cursor: canJump ? 'pointer' : 'default',
              transition: 'background-color 0.14s ease, border-color 0.14s ease',
              '&:hover': canJump ? { backgroundColor: '#EEF6FE', borderColor: '#93C5FD' } : undefined,
            }}
            role={canJump ? 'button' : undefined}
            tabIndex={canJump ? 0 : undefined}
            aria-label={canJump ? t('Mở trang {0} trong CV để kiểm tra bằng chứng', page || '') : undefined}
            onClick={() => { if (canJump && page) onJumpToPage(page, result.criterion_id); }}
            onKeyDown={event => { if (canJump && page && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onJumpToPage(page, result.criterion_id); } }}
          >
            <Typography variant="body2" sx={{ fontStyle: 'italic', color: '#1E293B', fontSize: 13, lineHeight: 1.65 }}>
              &ldquo;{quote}&rdquo;
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
              {canJump ? (
                <Button
                  size="small"
                  variant="text"
                  endIcon={<OpenInNewIcon sx={{ fontSize: '13px !important' }} />}
                  sx={{ py: 0.25, px: 1, fontSize: 11.5, color: '#0A2B57', fontWeight: 600 }}
                  onClick={e => { e.stopPropagation(); if (page) onJumpToPage(page, result.criterion_id); }}
                >
                  {t('Trang {0} · Đã xác minh', page)}
                </Button>
              ) : (
                <Chip
                  label={!verified ? t('Trích dẫn chưa xác minh') : t('Đoạn trích đã xác minh')}
                  size="small"
                  sx={{
                    backgroundColor: verified ? '#EEF4FC' : '#FFFAEB',
                    color: verified ? '#0A2B57' : '#B54708',
                    fontWeight: 600,
                    fontSize: 11,
                    height: 21,
                  }}
                />
              )}
            </Box>
          </Paper>
        ) : (
          <Paper elevation={0} sx={{ backgroundColor: '#FFFBEB', border: '1px solid #FDE68A', p: 1.25, borderRadius: '8px', mt: 1 }}>
            <Typography variant="caption" sx={{ color: '#92400E', fontWeight: 500 }}>
              {t('Chưa có bằng chứng được trích xuất cho tiêu chí này.')}
            </Typography>
          </Paper>
        )}

        {result.outcome === 'UNCLEAR' && (
          <Alert severity="warning" icon={false} sx={{ mt: 1.5, py: 0.25, fontSize: 12 }}>
            {t('Không tìm thấy bằng chứng rõ ràng. Vui lòng kiểm tra CV để xác minh.')}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
