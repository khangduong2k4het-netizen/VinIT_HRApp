'use client';

/**
 * Khối "Lịch phỏng vấn" trong hồ sơ ứng viên.
 *
 * Vì sao đặt ở đây chứ không phải một màn riêng: HR đang đứng trong hồ sơ khi
 * quyết định mời phỏng vấn. Bắt họ rời sang màn khác rồi tìm lại đúng ứng viên
 * là thêm hai bước cho một quyết định đã có trong đầu.
 *
 * Ba điều cố ý:
 *
 * 1. **Luôn hiện "giờ Việt Nam (GMT+7)"** cạnh giờ hẹn. Lịch lưu UTC, nên nếu
 *    chỉ hiện "14:00" thì người đặt và người dự có thể hiểu hai múi giờ khác nhau.
 * 2. **Nút "Tạo scorecard" chỉ hiện khi buổi đã DONE** — chấm trước khi phỏng
 *    vấn là chấm dự đoán, và máy chủ cũng chặn (409).
 * 3. **Huỷ không xoá.** Buổi đã huỷ vẫn nằm trong danh sách, để lịch sử nói đúng
 *    "đã huỷ rồi xếp lại" thay vì che mất lần huỷ.
 */
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, MenuItem, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useI18n } from '@/i18n/I18nProvider';
import { interviewsApi, usersApi } from '@/lib/api';

export type Interview = {
  interview_id: string;
  application_id: string;
  round_number: number;
  status: 'SCHEDULED' | 'DONE' | 'CANCELLED' | 'NO_SHOW';
  starts_at: string;
  ends_at: string;
  location_kind: 'ONSITE' | 'ONLINE' | 'PHONE';
  location_text: string | null;
  participant_count: number;
  submitted_scorecards: number;
  total_scorecards: number;
  participants?: Array<{ user_id: string; participant_role: string; display_name?: string | null }>;
};

const STATUS_LABEL: Record<Interview['status'], string> = {
  SCHEDULED: 'Đã hẹn',
  DONE: 'Đã diễn ra',
  CANCELLED: 'Đã huỷ',
  NO_SHOW: 'Ứng viên không đến',
};

const LOCATION_LABEL: Record<Interview['location_kind'], string> = {
  ONSITE: 'Tại văn phòng',
  ONLINE: 'Trực tuyến',
  PHONE: 'Qua điện thoại',
};

const TIME_ZONE = 'Asia/Ho_Chi_Minh';

/** Giờ Việt Nam kèm nhãn múi giờ — không bao giờ hiện giờ trần. */
export function formatVietnamTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const formatted = new Intl.DateTimeFormat('vi-VN', {
    timeZone: TIME_ZONE, day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date);
  return `${formatted} (GMT+7)`;
}

/** `<input type="datetime-local">` cho giờ Việt Nam → ISO UTC để gửi máy chủ. */
export function vietnamLocalToUtc(local: string): string {
  // Chuỗi dạng "2026-12-01T14:00" — Việt Nam là UTC+7 cố định, không có DST,
  // nên cộng 7 giờ là đủ và không cần thư viện múi giờ.
  const withSeconds = local.length === 16 ? `${local}:00` : local;
  return `${withSeconds}+07:00`;
}

export default function InterviewPanel({ applicationId }: { applicationId: string }) {
  const { t } = useI18n();
  const router = useRouter();
  const [items, setItems] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [round, setRound] = useState('1');
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');
  const [locationKind, setLocationKind] = useState<'ONSITE' | 'ONLINE' | 'PHONE'>('ONSITE');
  const [locationText, setLocationText] = useState('');
  // Máy chủ đòi ít nhất một người phỏng vấn: một buổi không có người chấm là
  // buổi không ai chấm được. Vì vậy dialog phải chọn được người ngay tại đây,
  // nếu không nút "Đặt lịch" sẽ luôn trả 400.
  const [people, setPeople] = useState<Array<{ user_id: string; display_name: string }>>([]);
  const [reviewers, setReviewers] = useState<Array<{ user_id: string; display_name: string }>>([]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const response = await interviewsApi.list({});
      const all: Interview[] = response.data;
      setItems(all.filter(item => item.application_id === applicationId));
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không tải được lịch phỏng vấn.'));
    } finally { setLoading(false); }
  }, [applicationId, t]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    // Chỉ tải danh bạ khi mở dialog — không tải ở lần render đầu để không thêm
    // một request vào mỗi lần mở hồ sơ.
    if (!open || people.length) return;
    usersApi.list()
      .then(response => setPeople(response.data || []))
      .catch(() => setPeople([]));
  }, [open, people.length]);

  const resetForm = () => {
    setRound('1'); setStartsAt(''); setEndsAt(''); setLocationKind('ONSITE');
    setLocationText(''); setFormError(null); setReviewers([]);
  };

  const submit = async () => {
    if (!startsAt || !endsAt) { setFormError(t('Cần nhập giờ bắt đầu và kết thúc.')); return; }
    if (!reviewers.length) { setFormError(t('Cần chọn ít nhất một người phỏng vấn.')); return; }
    setSaving(true); setFormError(null);
    try {
      await interviewsApi.create({
        application_id: applicationId,
        round_number: Number(round),
        starts_at: vietnamLocalToUtc(startsAt),
        ends_at: vietnamLocalToUtc(endsAt),
        location_kind: locationKind,
        location_text: locationText.trim() || null,
        participants: reviewers.map(person => ({ user_id: person.user_id, participant_role: 'INTERVIEWER' as const })),
      });
      setSuccess(t('Đã đặt lịch phỏng vấn.'));
      setOpen(false); resetForm();
      await load();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || t('Không đặt được lịch.'));
    } finally { setSaving(false); }
  };

  const setStatus = async (item: Interview, status: Interview['status']) => {
    setError(null); setSuccess(null);
    try {
      await interviewsApi.changeStatus(item.interview_id, status);
      setSuccess(t('Đã cập nhật trạng thái buổi phỏng vấn.'));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không đổi được trạng thái buổi.'));
    }
  };

  const createScorecards = async (item: Interview) => {
    setError(null); setSuccess(null);
    try {
      const response = await interviewsApi.createScorecards(item.interview_id);
      setSuccess(t('Đã tạo {0} phiếu chấm điểm.').replace('{0}', String(response.data.created)));
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không tạo được phiếu chấm điểm.'));
    }
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6">{t('Lịch phỏng vấn')}</Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={() => { resetForm(); setOpen(true); }}>
          {t('Đặt lịch')}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 1 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 1 }} onClose={() => setSuccess(null)}>{success}</Alert>}

      {loading ? <CircularProgress size={20} /> : !items.length ? (
        <Typography variant="body2" color="text.secondary">{t('Chưa có buổi phỏng vấn nào.')}</Typography>
      ) : items.map(item => <Box key={item.interview_id}
        sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, mb: 1 }}>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="body2" fontWeight={600}>{t('Vòng')} {item.round_number}</Typography>
          <Chip size="small" label={t(STATUS_LABEL[item.status])}
            color={item.status === 'SCHEDULED' ? 'info' : item.status === 'DONE' ? 'success' : 'default'}
            variant="outlined" />
          <Typography variant="body2">{formatVietnamTime(item.starts_at)}</Typography>
          <Typography variant="caption" color="text.secondary">
            {t(LOCATION_LABEL[item.location_kind])}{item.location_text ? ` · ${item.location_text}` : ''}
          </Typography>
        </Box>
        {item.total_scorecards > 0 && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
          {t('Phiếu chấm đã nộp: {0}/{1}').replace('{0}', String(item.submitted_scorecards)).replace('{1}', String(item.total_scorecards))}
        </Typography>}
        <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
          {item.status === 'SCHEDULED' && <>
            <Button size="small" onClick={() => void setStatus(item, 'DONE')}>{t('Đã diễn ra')}</Button>
            <Button size="small" color="warning" onClick={() => void setStatus(item, 'CANCELLED')}>{t('Huỷ buổi')}</Button>
            <Button size="small" color="warning" onClick={() => void setStatus(item, 'NO_SHOW')}>{t('Ứng viên không đến')}</Button>
          </>}
          {item.status === 'DONE' && item.total_scorecards === 0 && (
            <Button size="small" onClick={() => void createScorecards(item)}>{t('Tạo phiếu chấm điểm')}</Button>
          )}
          {/* Trước đây bấm "Tạo phiếu chấm điểm" xong là hết đường: phiếu đã có
              trong DB nhưng không nút nào mở ra được. Nút này là lối đi tiếp. */}
          {item.total_scorecards > 0 && (
            <Button size="small" variant="contained"
              onClick={() => router.push(`/interviews/${item.interview_id}`)}>
              {item.submitted_scorecards < item.total_scorecards ? t('Chấm điểm') : t('Xem phiếu chấm')}
            </Button>
          )}
        </Box>
      </Box>)}
      {items.length > 0 && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
        {t('Giờ hẹn hiện theo giờ Việt Nam (GMT+7).')}
      </Typography>}

      <Dialog open={open} onClose={() => !saving && setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('Đặt lịch phỏng vấn')}</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mb: 1 }}>{t(formError)}</Alert>}
          <TextField select fullWidth margin="dense" label={t('Vòng')} value={round}
            onChange={event => setRound(event.target.value)}>
            {[1, 2, 3, 4, 5].map(value => <MenuItem key={value} value={String(value)}>{value}</MenuItem>)}
          </TextField>
          <TextField fullWidth margin="dense" type="datetime-local" label={t('Bắt đầu (giờ Việt Nam)')}
            value={startsAt} onChange={event => setStartsAt(event.target.value)}
            InputLabelProps={{ shrink: true }} />
          <TextField fullWidth margin="dense" type="datetime-local" label={t('Kết thúc (giờ Việt Nam)')}
            value={endsAt} onChange={event => setEndsAt(event.target.value)}
            InputLabelProps={{ shrink: true }} />
          <Autocomplete
            multiple
            options={people}
            value={reviewers}
            onChange={(_, value) => setReviewers(value)}
            getOptionLabel={option => option.display_name || option.user_id}
            isOptionEqualToValue={(option, value) => option.user_id === value.user_id}
            renderInput={params => <TextField {...params} margin="dense" label={t('Người phỏng vấn')}
              helperText={t('Mỗi người sẽ nhận một phiếu chấm điểm sau khi buổi diễn ra.')} />}
            sx={{ mt: 1 }}
          />
          <TextField select fullWidth margin="dense" label={t('Hình thức')} value={locationKind}
            onChange={event => setLocationKind(event.target.value as typeof locationKind)}>
            {Object.entries(LOCATION_LABEL).map(([value, label]) =>
              <MenuItem key={value} value={value}>{t(label)}</MenuItem>)}
          </TextField>
          <TextField fullWidth margin="dense" label={t('Phòng họp / link / số điện thoại')}
            value={locationText} onChange={event => setLocationText(event.target.value)}
            helperText={locationKind === 'ONSITE'
              ? t('Có thể để trống nếu chưa chốt phòng.')
              : t('Bắt buộc với buổi trực tuyến hoặc qua điện thoại.')} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={saving}>{t('Hủy')}</Button>
          <Button variant="contained" onClick={submit} disabled={saving}>
            {saving ? t('Đang lưu…') : t('Đặt lịch')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
