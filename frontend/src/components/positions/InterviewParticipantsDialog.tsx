'use client';

/**
 * Sửa người phỏng vấn của một buổi **chưa diễn ra**.
 *
 * Vì sao cần: trước đây, một người báo ốm trước buổi là phải huỷ cả buổi rồi tạo
 * lại. Cách đó xoá lịch sử "buổi này đã từng có ai", và với buổi đã `DONE` thì
 * không tạo lại được cùng vòng.
 *
 * Cố ý **gửi toàn bộ danh sách**, không gửi từng thao tác thêm/bớt: người dùng
 * đang nhìn một danh sách và sửa nó; gửi hiệu thêm/bớt thì hai người sửa cùng
 * lúc sẽ ra kết quả phụ thuộc thứ tự.
 *
 * Cố ý **không** cho tự thêm người không có tài khoản: mỗi người phỏng vấn phải
 * có một phiếu chấm, mà phiếu cần một `reviewer_user_id`.
 */

import { useEffect, useState } from 'react';
import {
  Alert, Autocomplete, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography,
} from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { interviewsApi, usersApi } from '@/lib/api';
import type { Interview } from './InterviewPanel';

type Person = { user_id: string; display_name: string };

export default function InterviewParticipantsDialog({ interview, open, onClose, onSaved }: {
  interview: Interview | null;
  open: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { t } = useI18n();
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<Person[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    // Nạp danh bạ mỗi lần mở: người mới vào công ty phải chọn được ngay, và danh
    // bạch không đủ lớn để đáng giữ cache qua nhiều phiên.
    usersApi.list().then(res => setPeople(res.data || [])).catch(() => setPeople([]));
    const current = (interview?.participants || [])
      .filter(p => p.participant_role === 'INTERVIEWER')
      .map(p => ({ user_id: p.user_id, display_name: p.display_name || p.user_id }));
    setSelected(current);
  }, [open, interview]);

  const submit = async () => {
    if (!interview) return;
    if (!selected.length) { setError(t('Cần chọn ít nhất một người phỏng vấn. Muốn bỏ hết thì huỷ buổi.')); return; }
    setSaving(true); setError(null);
    try {
      await interviewsApi.replaceParticipants(interview.interview_id,
        selected.map(person => ({ user_id: person.user_id, participant_role: 'INTERVIEWER' })));
      onSaved(t('Đã cập nhật người phỏng vấn.'));
      onClose();
    } catch (err: any) {
      // 409 ở đây thường là "người này đã có phiếu chấm" — câu của máy chủ đã nêu
      // tên, nên hiện nguyên văn thay vì nuốt thành "có lỗi xảy ra".
      setError(err.response?.data?.detail || t('Không cập nhật được người phỏng vấn.'));
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onClose={() => !saving && onClose()} maxWidth="sm" fullWidth>
      <DialogTitle>{t('Người phỏng vấn')}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('Mỗi người phỏng vấn nhận một phiếu chấm điểm. Người bị bỏ khỏi buổi sẽ nhận thông báo trong ứng dụng.')}
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 1 }}>{t(error)}</Alert>}
        <Autocomplete
          multiple
          options={people}
          value={selected}
          onChange={(_, value) => setSelected(value)}
          getOptionLabel={option => option.display_name || option.user_id}
          isOptionEqualToValue={(option, value) => option.user_id === value.user_id}
          renderInput={params => <TextField {...params} margin="dense" label={t('Người phỏng vấn')} />}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>{t('Hủy')}</Button>
        <Button variant="contained" onClick={() => void submit()} disabled={saving || !interview}>
          {saving ? t('Đang lưu…') : t('Lưu')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
