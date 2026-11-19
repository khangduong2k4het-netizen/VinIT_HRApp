'use client';

import * as React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { useI18n } from '@/i18n/I18nProvider';
import { formatFileSize, validateIntakeFiles } from '@/lib/intake';

interface CVIntakePanelProps {
  files: File[];
  onFiles: (files: File[]) => void;
  onRemove: (index: number) => void;
  onUpload: () => void;
  uploading: boolean;
  uploadProgress: number;
  disabled?: boolean;
  error?: string | null;
}

export default function CVIntakePanel({ files, onFiles, onRemove, onUpload, uploading, uploadProgress, disabled, error }: CVIntakePanelProps) {
  const { t } = useI18n();
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = React.useState(false);
  const validation = validateIntakeFiles(files);
  const canUpload = files.length > 0 && !validation.batchError && !uploading && !disabled;

  return (
    <Card id="cv-intake" variant="outlined" sx={{ mb: 3, borderColor: dragging ? '#2599DC' : '#D8E2EE', backgroundColor: dragging ? '#EFF8FF' : '#FFFFFF' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <Box>
            <Typography variant="h3" sx={{ fontSize: 17, color: '#0A2B57' }}>{t("Tiếp nhận CV")}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t("Kéo thả hoặc chọn tệp PDF/DOCX/JPG/PNG (tối đa 10 MB mỗi tệp). Hệ thống kiểm tra định dạng và dung lượng trước khi gửi.")}
            </Typography>
            <Typography variant="caption" color="text.secondary">{t("Tối đa 50 file, mỗi file ≤ 10MB, tổng lô ≤ 250MB")}</Typography>
          </Box>
          <Button variant="outlined" startIcon={<UploadFileIcon />} disabled={disabled || uploading} onClick={() => inputRef.current?.click()}>
            {t("Chọn tệp CV")}
          </Button>
        </Box>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.jpg,.jpeg,.png,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/jpeg,image/png"
          onChange={event => {
            onFiles(Array.from(event.target.files || []));
            event.target.value = '';
          }}
          style={{ display: 'none' }}
          aria-label={t("Chọn tệp CV")}
        />

        <Box
          onDragOver={event => { event.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={event => {
            event.preventDefault();
            setDragging(false);
            onFiles(Array.from(event.dataTransfer.files || []));
          }}
          sx={{ border: '2px dashed #CBD5E1', borderRadius: 2, p: 3, textAlign: 'center', backgroundColor: '#F8FAFC' }}
        >
          <UploadFileIcon sx={{ color: '#134D8B', fontSize: 36, mb: 1 }} aria-hidden />
          <Typography variant="body2" fontWeight={600}>{t("Kéo thả tệp CV vào đây")}</Typography>
          <Typography variant="caption" color="text.secondary">{t("Kiểm tra từng tệp ở danh sách bên dưới trước khi bắt đầu xử lý.")}</Typography>
        </Box>

        {(error || validation.batchError) && <Alert severity="error" sx={{ mt: 2 }}>{t(error || validation.batchError || '')}</Alert>}

        {files.length > 0 && (
          <>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mt: 2, mb: 1 }}>
              <Typography variant="body2" fontWeight={700}>{t("Đã chọn {0} tệp", files.length)} · {formatFileSize(validation.totalBytes)}</Typography>
              <Typography variant="caption" color="text.secondary">{t("Tên tệp trùng chỉ là cảnh báo kiểm tra, không tự kết luận hồ sơ trùng.")}</Typography>
            </Box>
            <List dense sx={{ maxHeight: 280, overflowY: 'auto', border: '1px solid #EDF1F5', borderRadius: 2 }}>
              {validation.items.map((item, index) => (
                <ListItem
                  key={`${item.name}-${index}`}
                  secondaryAction={(
                    <Tooltip title={t("Loại bỏ tệp")}>
                      <IconButton edge="end" size="small" onClick={() => onRemove(index)} disabled={uploading} aria-label={t("Loại bỏ tệp {0}", item.name)}>
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                  sx={{ pr: 6 }}
                >
                  <ListItemText
                    primary={<Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{item.name} <Typography component="span" variant="caption" color="text.secondary">({formatFileSize(item.size)})</Typography></Typography>}
                    secondary={t(item.message)}
                  />
                  <Chip
                    size="small"
                    label={item.status === 'VALID' ? t("Hợp lệ") : item.status === 'WARNING' ? t("Cần kiểm tra") : t("Chưa hợp lệ")}
                    color={item.status === 'VALID' ? 'success' : item.status === 'WARNING' ? 'warning' : 'error'}
                    variant="outlined"
                    sx={{ mr: 1 }}
                  />
                </ListItem>
              ))}
            </List>
          </>
        )}

        {uploading && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress variant="determinate" value={uploadProgress} />
            <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>{t("Đang tải lên:")} {uploadProgress}%</Typography>
          </Box>
        )}

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          <Button variant="contained" color="secondary" onClick={onUpload} disabled={!canUpload}>
            {uploading ? t("Đang tải...") : t("Bắt đầu xử lý")}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
