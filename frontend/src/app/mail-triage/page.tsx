'use client';

// F3.03 email channel: CVs received by email. HR places those HRA could not match to a position.
import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, MenuItem, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import Link from 'next/link';
import { mailboxApi, positionsApi, type MailboxStatus } from '@/lib/api';
import { useI18n } from '@/i18n/I18nProvider';

type Attachment = { attachment_id: string; filename: string; mime_type: string | null; size_bytes: number | null; status: string; reject_reason: string | null };
type Suggestion = { position_id: string; position_code: string; title: string };
type Item = {
  message_id: string; from_address: string | null; from_name: string | null; subject: string | null;
  received_at: string | null; created_at: string; status: MailboxStatus; reason: string | null; match_method: string | null;
  suggestions: Suggestion[]; position_id: string | null; position_code: string | null; position_title: string | null;
  application_id: string | null; attachments: Attachment[];
};

const REASONS: Record<string, string> = {
  NO_CODE: 'Thư không có mã vị trí',
  UNKNOWN_CODE: 'Mã vị trí trong thư không tồn tại',
  MULTIPLE_CODES: 'Thư có nhiều mã vị trí khác nhau',
  POSITION_NOT_OPEN: 'Vị trí chưa mở hoặc chưa có bộ tiêu chí được duyệt',
  POSITION_BUSY: 'Vị trí đang bận, thử lại sau',
  NO_CV_ATTACHMENT: 'Không có file CV hợp lệ (PDF, DOCX, JPG, PNG)',
  AUTO_REPLY: 'Thư trả lời tự động',
  OWN_MESSAGE: 'Thư do chính hộp thư này gửi',
  DUPLICATE_MESSAGE: 'Thư đã nhận trước đó',
  DUPLICATE_CV: 'CV này đã có trong vị trí',
  HR_IGNORED: 'HR đã bỏ qua',
  SCAN_UNAVAILABLE: 'Không quét được mã độc lúc nhận thư',
};
const METHODS: Record<string, string> = {
  PLUS_ADDRESS: 'theo địa chỉ +mã', SUBJECT_CODE: 'theo mã trong tiêu đề', BODY_CODE: 'theo mã trong thư',
  FILENAME_CODE: 'theo mã trong tên file', HR: 'HR chọn',
};
const TABS: { value: MailboxStatus; label: string }[] = [
  { value: 'NEEDS_TRIAGE', label: 'Chờ phân loại' },
  { value: 'MATCHED', label: 'Đã vào hồ sơ' },
  { value: 'IGNORED', label: 'Bỏ qua' },
  { value: 'FAILED', label: 'Lỗi' },
];

export default function MailTriagePage() {
  const { t, dateLocale } = useI18n();
  const [tab, setTab] = useState<MailboxStatus>('NEEDS_TRIAGE');
  const [items, setItems] = useState<Item[] | null>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setItems(null);
    try {
      const data: Item[] = (await mailboxApi.messages(tab)).data.items;
      setItems(data);
      setChoice(prev => {
        const next = { ...prev };
        data.forEach(item => { if (!next[item.message_id] && item.suggestions?.[0]) next[item.message_id] = item.suggestions[0].position_id; });
        return next;
      });
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể tải hộp thư CV.')); setItems([]); }
  }, [tab, t]);
  useEffect(() => { load(); }, [load]);
  // All open positions (the plain list endpoint returns one page of 20).
  useEffect(() => { positionsApi.listAll().then(all => setPositions(all.filter((p: any) => p.status === 'OPEN'))).catch(() => setPositions([])); }, []);

  const open = async (att: Attachment) => {
    try {
      const res = await mailboxApi.attachmentFile(att.attachment_id);
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch { setError(t('Không mở được file.')); }
  };
  const assign = async (item: Item) => {
    const positionId = choice[item.message_id];
    if (!positionId) return;
    try {
      setBusy(item.message_id); setError(null);
      const res = await mailboxApi.assign(item.message_id, positionId);
      setNotice(res.data.status === 'DUPLICATE' ? t('CV này đã có trong vị trí, không tạo hồ sơ mới.') : t('Đã đưa CV vào vị trí. Hệ thống đang đọc và chấm CV.'));
      await load();
    } catch (err: any) { setError(err.response?.data?.detail || t('Không thể đưa CV vào vị trí.')); }
    finally { setBusy(null); }
  };
  const ignore = async (item: Item) => {
    try { setBusy(item.message_id); setError(null); await mailboxApi.ignore(item.message_id); setNotice(t('Đã bỏ qua thư.')); await load(); }
    catch (err: any) { setError(err.response?.data?.detail || t('Không thể bỏ qua thư.')); }
    finally { setBusy(null); }
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 1 }}>{t('Hộp thư CV')}</Typography>
      <Typography color="text.secondary" sx={{ mb: 2, maxWidth: 760 }}>
        {t('CV ứng viên gửi qua email. Thư có mã vị trí được tự động đưa vào hồ sơ; thư không rõ vị trí nằm ở mục "Chờ phân loại" để HR chọn.')}
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{t(error)}</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }} variant="scrollable" allowScrollButtonsMobile>
        {TABS.map(x => <Tab key={x.value} value={x.value} label={t(x.label)} />)}
      </Tabs>
      {items === null ? <CircularProgress size={24} /> : items.length === 0 ? (
        <Typography color="text.secondary">{tab === 'NEEDS_TRIAGE' ? t('Không có thư nào chờ phân loại.') : t('Chưa có thư nào.')}</Typography>
      ) : (
        <Stack spacing={1.5}>
          {items.map(item => (
            <Card key={item.message_id} variant="outlined">
              <CardContent sx={{ '&:last-child': { pb: 2 } }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ sm: 'flex-start' }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography fontWeight={600} sx={{ wordBreak: 'break-word' }}>{item.subject || t('(không có tiêu đề)')}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-all' }}>
                      {item.from_name ? `${item.from_name} · ` : ''}{item.from_address || ''} · {new Date(item.received_at || item.created_at).toLocaleString(dateLocale)}
                    </Typography>
                  </Box>
                  {item.reason && <Chip size="small" variant="outlined" color={tab === 'FAILED' ? 'error' : 'default'} label={t(REASONS[item.reason] || item.reason)} />}
                </Stack>
                <Stack direction="row" spacing={1} sx={{ mt: 1.25 }} flexWrap="wrap" useFlexGap>
                  {item.attachments.map(att => (
                    <Chip key={att.attachment_id} size="small" icon={<AttachFileIcon />} label={att.filename}
                      onClick={tab === 'NEEDS_TRIAGE' && att.status === 'STORED' ? () => open(att) : undefined}
                      color={att.status === 'USED' ? 'success' : att.status === 'REJECTED' ? 'error' : 'default'}
                      variant={att.status === 'STORED' ? 'filled' : 'outlined'} />
                  ))}
                </Stack>
                {tab === 'MATCHED' && item.position_code && (
                  <Typography variant="body2" sx={{ mt: 1.25 }}>
                    {t('Vào vị trí')} <b>{item.position_code}</b> {item.position_title ? `– ${item.position_title}` : ''} ({t(METHODS[item.match_method || ''] || '')})
                    {item.application_id && item.position_id && <> · <Link href={`/positions/${item.position_id}/applicants/${item.application_id}`}>{t('Mở hồ sơ')}</Link></>}
                  </Typography>
                )}
                {tab === 'NEEDS_TRIAGE' && (
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mt: 1.5 }} alignItems={{ sm: 'center' }}>
                    {item.suggestions?.length > 0 && (
                      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>{t('Gợi ý:')}</Typography>
                        {item.suggestions.map(s => (
                          <Chip key={s.position_id} size="small" color="primary" variant={choice[item.message_id] === s.position_id ? 'filled' : 'outlined'}
                            label={`${s.position_code} · ${s.title}`} onClick={() => setChoice(c => ({ ...c, [item.message_id]: s.position_id }))} />
                        ))}
                      </Stack>
                    )}
                    <TextField select size="small" label={t('Đưa vào vị trí')} value={choice[item.message_id] || ''} sx={{ minWidth: 260, flex: 1 }}
                      onChange={e => setChoice(c => ({ ...c, [item.message_id]: e.target.value }))}>
                      {positions.map(p => <MenuItem key={p.position_id} value={p.position_id}>{p.position_code} · {p.title}</MenuItem>)}
                    </TextField>
                    <Button variant="contained" color="secondary" onClick={() => assign(item)} disabled={!choice[item.message_id] || busy === item.message_id}>
                      {busy === item.message_id ? <CircularProgress size={18} color="inherit" /> : t('Đưa vào hồ sơ')}
                    </Button>
                    <Button color="inherit" onClick={() => ignore(item)} disabled={busy === item.message_id}>{t('Bỏ qua')}</Button>
                  </Stack>
                )}
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
  );
}
