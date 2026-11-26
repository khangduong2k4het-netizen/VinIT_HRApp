'use client';

import { useI18n } from '@/i18n/I18nProvider';

import * as React from 'react';
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, CircularProgress, TextField, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { PrivateNote } from '@/types';

interface HRNotesPanelProps {
  /** Ghi chú chung của hồ sơ; ghi chú theo tiêu chí nằm cạnh tiêu chí đó. */
  notes: PrivateNote[];
  loading: boolean;
  error: string | null;
  onAdd: (content: string) => Promise<void>;
  /**
   * Gọi ở lần mở panel đầu tiên. Trang không tự tải ghi chú khi mở hồ sơ —
   * panel đóng thì nội dung không ai đọc, nên request chỉ nên có khi có người mở.
   */
  onOpen?: () => void;
  /** Số ghi chú đang gắn với tiêu chí, để không ai nghĩ danh sách này là tất cả. */
  criterionNoteCount?: number;
}

export default function HRNotesPanel({ notes, loading, error, onAdd, onOpen, criterionNoteCount = 0 }: HRNotesPanelProps) {
  const { t, dateLocale } = useI18n();
  const [content, setContent] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState<string | null>(null);

  const add = async () => {
    if (!content.trim() || saving) return;
    try {
      setSaving(true);
      setSaveError(null);
      await onAdd(content.trim());
      setContent('');
    } catch (err: any) {
      setSaveError(err.response?.data?.detail || t('Không thể lưu ghi chú.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Accordion
      id="hr-notes"
      disableGutters
      elevation={0}
      // Mở panel là lúc duy nhất cần dữ liệu; đóng/mở lại không hỏi lại.
      onChange={(_event, expanded) => { if (expanded) onOpen?.(); }}
      sx={{ mb: 3, border: '1px solid #E4E7EC', borderRadius: '8px !important', '&:before': { display: 'none' } }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography fontWeight={600}>{t("Ghi chú nội bộ HR ")}{notes.length > 0 ? `(${notes.length})` : ''}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Alert severity="info" sx={{ mb: 2 }}>{t("Chỉ HR phụ trách và HR Lead được xem. Ghi chú không được chia sẻ với Hiring Manager hoặc gửi cho AI. Các ghi chú được lưu nối tiếp để giữ lịch sử.")}</Alert>
        {criterionNoteCount > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }} data-testid="criterion-note-hint">
            {t('{0} ghi chú đang nằm cạnh tiêu chí tương ứng.', criterionNoteCount)}
          </Typography>
        )}
        {(error || saveError) && <Alert severity="error" sx={{ mb: 2 }}>{t(error || saveError || '')}</Alert>}
        <TextField label={t("Thêm ghi chú nội bộ")} fullWidth multiline minRows={2} value={content} onChange={e => setContent(e.target.value)} inputProps={{ maxLength: 5000 }} data-testid="hr-note-input" />
        <Button variant="outlined" size="small" sx={{ mt: 1.5, mb: 2 }} onClick={add} disabled={saving || !content.trim()} data-testid="hr-note-save">{saving ? t('Đang lưu...') : t("Thêm ghi chú")}</Button>
        {loading ? <Box><CircularProgress size={20} /></Box> : notes.length === 0 ? <Typography variant="body2" color="text.secondary">{t("Chưa có ghi chú nội bộ.")}</Typography> : notes.map(note => (
          <Box key={note.note_id} sx={{ borderTop: '1px solid #EDF1F5', py: 1.5 }}>
            <Typography variant="caption" color="text.secondary">{note.author_name || 'HR'} · {new Date(note.created_at).toLocaleString(dateLocale)}</Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{note.content}</Typography>
          </Box>
        ))}
      </AccordionDetails>
    </Accordion>
  );
}
