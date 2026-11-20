'use client';

import * as React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import type { CriterionReasonCandidate } from '@/lib/rejectionReasons';
import type { RequirementSpec } from '@/types';

/**
 * Chip gợi ý cho ô "Lý do loại hồ sơ".
 *
 * Chọn chip = điền vào ô nhập, không tự gửi gì: HR vẫn đọc lại, sửa và quyết
 * định. Cố ý không dùng combobox vì ô lý do là nhiều dòng, và một danh sách chip
 * đọc được ngay cả khi có nhiều câu dài.
 */
function requirementDetail(spec: RequirementSpec | null | undefined, t: (key: string, ...args: Array<string | number>) => string): string {
  if (!spec) return '';
  const parts: string[] = [];
  if (spec.min_years != null) parts.push(t('Tối thiểu {0} năm', spec.min_years));
  if (spec.required_degree_level != null) parts.push(t('Yêu cầu trình độ bậc {0}', spec.required_degree_level));
  const languages = (spec.required_languages || []).filter(Boolean);
  if (languages.length) parts.push(languages.join(', '));
  if (spec.required_ielts != null) parts.push(`IELTS ${spec.required_ielts}`);
  if (spec.required_toeic != null) parts.push(`TOEIC ${spec.required_toeic}`);
  if (spec.required_cefr) parts.push(`CEFR ${spec.required_cefr}`);
  if (spec.terms?.length) parts.push(spec.terms.filter(Boolean).join(', '));
  return parts.join(' · ');
}

interface ReasonSuggestionsProps {
  /** Lý do HR đã dùng cho vị trí này, mới nhất trước. */
  recent: string[];
  /** Tiêu chí bắt buộc chưa đạt của hồ sơ đang mở. */
  candidates: CriterionReasonCandidate[];
  onPick: (reason: string) => void;
  testId?: string;
}

export default function ReasonSuggestions({ recent, candidates, onPick, testId }: ReasonSuggestionsProps) {
  const { t } = useI18n();
  const suggestions: Array<{ text: string; recent: boolean }> = [];
  const seen = new Set<string>();
  const add = (text: string, isRecent: boolean) => {
    const normalized = text.trim();
    if (!normalized) return;
    const key = normalized.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    suggestions.push({ text: normalized, recent: isRecent });
  };

  recent.forEach(reason => add(reason, true));
  for (const candidate of candidates) {
    const detail = requirementDetail(candidate.spec, t) || candidate.name;
    add(
      candidate.outcome === 'NO_MATCH'
        ? t('Không đáp ứng: {0}', detail)
        : t('Chưa đủ bằng chứng: {0}', detail),
      false,
    );
  }

  if (!suggestions.length) return null;

  return (
    <Box sx={{ mb: 1.5 }} data-testid={testId || 'reason-suggestions'}>
      <Typography variant="caption" color="text.secondary">{t('Gợi ý lý do')}</Typography>
      <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mt: 0.5 }}>
        {suggestions.map(suggestion => (
          <Chip
            key={`${suggestion.recent ? 'recent' : 'criterion'}:${suggestion.text}`}
            size="small"
            label={suggestion.text}
            variant={suggestion.recent ? 'outlined' : 'filled'}
            onClick={() => onPick(suggestion.text)}
            data-testid={suggestion.recent ? 'reason-suggestion-recent' : 'reason-suggestion-criterion'}
            sx={{ height: 'auto', maxWidth: '100%', '& .MuiChip-label': { whiteSpace: 'normal', py: 0.5, lineHeight: 1.4 } }}
          />
        ))}
      </Box>
    </Box>
  );
}
