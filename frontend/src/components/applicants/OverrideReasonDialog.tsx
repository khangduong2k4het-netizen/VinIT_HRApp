'use client';

import { useI18n } from '@/i18n/I18nProvider';
import * as React from 'react';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Radio, RadioGroup, TextField, Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { applicationsApi } from '@/lib/api';

export interface OverrideCheck {
  is_override: boolean;
  direction: 'ADVANCED_DESPITE_AI' | 'REJECTED_DESPITE_AI' | null;
  ai_matching_status: string | null;
  ai_matching_score: number | null;
  ai_evidence_coverage: number | null;
  reason_codes: { code: string; label: string }[];
}

export interface OverrideDecision { overrideReasonCode?: string; overrideNote?: string }

const AI_STATUS_LABELS: Record<string, string> = {
  MEETS_MANDATORY: 'Đáp ứng bắt buộc', NEEDS_HR_VERIFICATION: 'Cần HR xác minh', POSSIBLE_MISMATCH: 'Cần xem xét',
};

/**
 * F2.03: before changing an application's status, ask the backend whether the
 * decision contradicts the AI conclusion; if so, collect a reason code.
 * `confirm` resolves to the extra fields to send, or `null` if HR cancelled.
 */
export function useOverrideGate() {
  const { t } = useI18n();
  const [pending, setPending] = useState<{ check: OverrideCheck; resolve: (value: OverrideDecision | null) => void } | null>(null);
  const [code, setCode] = useState('');
  const [note, setNote] = useState('');

  const confirm = useCallback(async (applicationId: string, newStatus: string): Promise<OverrideDecision | null> => {
    const res = await applicationsApi.checkOverride(applicationId, newStatus);
    const check: OverrideCheck = res.data;
    if (!check.is_override) return {};
    setCode(''); setNote('');
    return new Promise(resolve => setPending({ check, resolve }));
  }, []);

  const close = (value: OverrideDecision | null) => {
    pending?.resolve(value);
    setPending(null);
  };

  const check = pending?.check;
  const needsNote = code === 'OTHER' && !note.trim();
  const dialog = (
    <Dialog open={!!pending} onClose={() => close(null)} maxWidth="sm" fullWidth>
      <DialogTitle>{t("Quyết định khác kết luận của AI")}</DialogTitle>
      <DialogContent>
        {check && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {check.direction === 'ADVANCED_DESPITE_AI'
              ? t("AI kết luận “{0}” nhưng bạn đang đưa hồ sơ vào Shortlist.", t(AI_STATUS_LABELS[check.ai_matching_status || ''] || check.ai_matching_status || ''))
              : t("AI kết luận “{0}” nhưng bạn đang loại hồ sơ ở vòng sàng lọc.", t(AI_STATUS_LABELS[check.ai_matching_status || ''] || check.ai_matching_status || ''))}
            {check.ai_matching_score != null && ` ${t("Điểm AI: {0}", check.ai_matching_score)}.`}
          </Alert>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t("Chọn lý do điều chỉnh. Thông tin này giúp HR Lead cải tiến tiêu chí, không dùng để đánh giá cá nhân.")}
        </Typography>
        <RadioGroup value={code} onChange={e => setCode(e.target.value)}>
          {(check?.reason_codes || []).map(reason => (
            <FormControlLabel key={reason.code} value={reason.code} control={<Radio size="small" />} label={t(reason.label)} />
          ))}
        </RadioGroup>
        <TextField fullWidth multiline minRows={2} sx={{ mt: 1 }} value={note} onChange={e => setNote(e.target.value)}
          label={code === 'OTHER' ? t("Ghi chú (bắt buộc)") : t("Ghi chú (tùy chọn)")} inputProps={{ maxLength: 2000 }}
          error={code === 'OTHER' && !note.trim()} />
      </DialogContent>
      <DialogActions>
        <Button onClick={() => close(null)}>{t("Hủy")}</Button>
        <Button variant="contained" color="secondary" disabled={!code || needsNote}
          onClick={() => close({ overrideReasonCode: code, overrideNote: note.trim() || undefined })}>{t("Xác nhận quyết định")}</Button>
      </DialogActions>
    </Dialog>
  );
  return { confirm, dialog };
}
