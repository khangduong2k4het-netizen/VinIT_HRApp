'use client';
/**
 * Danh sách tệp bị từ chối, trình bày theo việc HR phải làm.
 *
 * Trước đây mỗi tệp chỉ hiện "Tệp không hợp lệ hoặc vượt giới hạn." — đúng nhưng
 * vô dụng: HR không biết là sai định dạng hay quá nặng, và không biết tệp đó có
 * tạo ra hồ sơ hay không. Ba trạng thái, ba câu khác nhau:
 *   - có application_id  → "đã tạo hồ sơ, bấm để mở" (kèm lý do)
 *   - không có           → "không tạo hồ sơ, chỉ cần tải lại đúng định dạng"
 *   - lý do lạ           → câu trung tính, không đoán bừa
 */
import Link from 'next/link';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useI18n } from '@/i18n/I18nProvider';
import { explainInvalidFile, type InvalidFileReason } from '@/lib/invalidFileReason';

export interface InvalidFile {
  original_filename: string;
  error_code?: string | null;
  application_id?: string | null;
}

const REASON_TEXT: Record<InvalidFileReason, string> = {
  TOO_LARGE: 'Tệp quá lớn so với giới hạn cho phép.',
  NOT_PDF_OR_DOCX: 'Tệp không phải PDF hoặc DOCX đọc được.',
  EMPTY: 'Tệp rỗng hoặc không đọc được nội dung.',
  CREATED_APPLICATION: '',
  UNKNOWN: 'Tệp không hợp lệ.',
};

export default function InvalidFileList({ files, positionId }: { files: InvalidFile[]; positionId?: string }) {
  const { t } = useI18n();
  if (!files.length) return null;
  return (
    <Box sx={{ mt: 1 }}>
      {files.map((file, index) => {
        const reason = explainInvalidFile(file.error_code);
        const detail = reason === 'UNKNOWN' ? '' : ` ${t(REASON_TEXT[reason])}`;
        return (
          <Typography key={`${file.original_filename}-${index}`} variant="caption" display="block" color="error.main">
            {file.original_filename}:{detail}{' '}
            {file.application_id && positionId ? (
              // Opens the profile that already exists for this rejected file, so
              // HR does not have to guess which row in the ranking page it became.
              <Link href={`/positions/${positionId}/applicants/${file.application_id}`}>
                {t('Hồ sơ đã được tạo nhưng cần HR kiểm tra — mở hồ sơ')}
              </Link>
            ) : (
              <span>{t('Tệp này không tạo hồ sơ — chỉ cần tải lại đúng định dạng.')}</span>
            )}
          </Typography>
        );
      })}
    </Box>
  );
}
