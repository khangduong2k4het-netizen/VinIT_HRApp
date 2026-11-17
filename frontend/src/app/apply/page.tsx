'use client';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container, FormControlLabel, Stack, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { fetchPublicPositions, submitApplication, validateCv, type ApplyFailure, type PublicPosition } from '@/lib/publicApply';

// Wording shown next to the tick boxes. HR / Legal must approve it before launch;
// when it changes, bump PUBLIC_INTAKE_NOTICE_VERSION on the backend so the stored
// consent records which version the candidate saw.
export default function ApplyPage() {
  const { t } = useI18n();
  const [positions, setPositions] = useState<PublicPosition[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<PublicPosition | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [consentProcessing, setConsentProcessing] = useState(false);
  const [consentPool, setConsentPool] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [fieldError, setFieldError] = useState<'MISSING' | 'TYPE' | 'SIZE' | 'CONSENT' | null>(null);
  const [failure, setFailure] = useState<ApplyFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try { setPositions(await fetchPublicPositions()); } catch { setPositions([]); setLoadError(true); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || busy) return;
    setFailure(null);
    const problem = validateCv(file);
    if (problem) { setFieldError(problem); return; }
    if (!consentProcessing) { setFieldError('CONSENT'); return; }
    setFieldError(null);
    setBusy(true);
    const result = await submitApplication(selected.code, file as File, consentPool, honeypot);
    setBusy(false);
    if (result.ok) setDone(true); else setFailure(result.failure);
  };

  const fieldMessage = fieldError === 'MISSING' ? t('Vui lòng chọn tệp CV.')
    : fieldError === 'TYPE' ? t('Chỉ hỗ trợ tệp PDF, DOCX, JPG hoặc PNG.')
    : fieldError === 'SIZE' ? t('Tệp vượt quá 10 MB.')
    : fieldError === 'CONSENT' ? t('Cần đồng ý cho phép xử lý hồ sơ để ứng tuyển.') : '';
  const failureMessage = failure === 'RATE_LIMIT' ? t('Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau.')
    : failure === 'UNAVAILABLE' ? t('Hệ thống tạm thời chưa nhận hồ sơ. Vui lòng thử lại sau.')
    : failure === 'POSITION_CLOSED' ? t('Vị trí không còn nhận hồ sơ.')
    : failure === 'FILE' ? t('Không thể nhận tệp này. Vui lòng kiểm tra định dạng (PDF, DOCX, JPG, PNG) và thử lại.')
    : failure === 'NETWORK' ? t('Không thể kết nối. Vui lòng thử lại.') : '';

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#F8FAFC' }}>
      <Box component="header" sx={{ bgcolor: 'primary.main', color: '#fff', py: 1.5 }}>
        <Container maxWidth="md" sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ bgcolor: '#fff', borderRadius: 1, px: 1, py: 0.5, display: 'flex' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/vinuni-logo.png" alt="VinUniversity" height={28} />
            </Box>
            <Typography component="h1" variant="h6" sx={{ fontWeight: 700 }}>{t('Cơ hội nghề nghiệp tại VinUni')}</Typography>
          </Stack>
          <LanguageSwitcher light />
        </Container>
      </Box>
      <Container maxWidth="md" sx={{ py: { xs: 3, md: 5 } }}>
        {done ? (
          <Alert severity="success" role="status">
            <Typography sx={{ fontWeight: 700 }}>{t('Đã nhận hồ sơ của bạn.')}</Typography>
            {t('Bộ phận Nhân sự sẽ xem xét hồ sơ và liên hệ nếu phù hợp.')}
          </Alert>
        ) : selected ? (
          <Card component="form" onSubmit={submit} noValidate>
            <CardContent>
              <Button size="small" onClick={() => { setSelected(null); setFailure(null); setFieldError(null); }}>{t('← Quay lại danh sách')}</Button>
              <Typography variant="h5" sx={{ fontWeight: 700, mt: 1 }}>{selected.title}</Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>{[selected.unit, selected.location].filter(Boolean).join(' · ')}</Typography>
              <Stack spacing={2}>
                <Box>
                  <Button variant="outlined" component="label">
                    {file ? file.name : t('Chọn tệp CV')}
                    <input type="file" hidden accept=".pdf,.docx,.jpg,.jpeg,.png"
                      onChange={e => { setFile(e.target.files?.[0] || null); setFieldError(null); }} />
                  </Button>
                  <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>{t('PDF, DOCX, JPG hoặc PNG, tối đa 10 MB.')}</Typography>
                </Box>
                <FormControlLabel
                  control={<Checkbox checked={consentProcessing} onChange={e => { setConsentProcessing(e.target.checked); setFieldError(null); }} />}
                  label={t('Tôi đồng ý cho VinUniversity xử lý hồ sơ này để xem xét ứng tuyển vào vị trí trên.')} />
                <FormControlLabel
                  control={<Checkbox checked={consentPool} onChange={e => setConsentPool(e.target.checked)} />}
                  label={t('Tôi đồng ý cho VinUniversity lưu hồ sơ tối đa 5 năm kể từ khi tôi đánh dấu đồng ý này và dùng lại để xem xét cho các vị trí khác phù hợp. Việc này không bắt buộc.')} />
                <Typography variant="caption" color="text.secondary">
                  {t('Bạn có thể yêu cầu rút đồng ý bất cứ lúc nào bằng cách liên hệ bộ phận Nhân sự. Hồ sơ không được dùng cho mục đích khác.')}
                </Typography>
                {/* Honeypot: invisible to people and assistive technology; bots fill it in. */}
                <Box aria-hidden="true" sx={{ position: 'absolute', left: '-10000px', width: 1, height: 1, overflow: 'hidden' }}>
                  <label>Website<input tabIndex={-1} autoComplete="off" value={honeypot} onChange={e => setHoneypot(e.target.value)} /></label>
                </Box>
                {fieldMessage && <Alert severity="error" role="alert">{fieldMessage}</Alert>}
                {failureMessage && <Alert severity="error" role="alert">{failureMessage}</Alert>}
                <Button type="submit" variant="contained" disabled={busy} sx={{ alignSelf: 'flex-start' }}>
                  {busy ? <CircularProgress size={20} aria-label={t('Đang gửi')} /> : t('Gửi hồ sơ')}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        ) : (
          <>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>{t('Vị trí đang tuyển')}</Typography>
            {positions === null && <CircularProgress aria-label={t('Đang tải')} />}
            {loadError && <Alert severity="error" action={<Button color="inherit" onClick={load}>{t('Thử lại')}</Button>}>{t('Không thể tải danh sách vị trí.')}</Alert>}
            {positions && !loadError && positions.length === 0 && <Alert severity="info">{t('Hiện chưa có vị trí nào đang nhận hồ sơ.')}</Alert>}
            <Stack spacing={1.5}>
              {(positions || []).map(position => (
                <Card key={position.code} variant="outlined">
                  <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                    <Box>
                      <Typography sx={{ fontWeight: 700 }}>{position.title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {[position.unit, position.location, position.employment_type].filter(Boolean).join(' · ')}
                      </Typography>
                    </Box>
                    <Button variant="contained" onClick={() => setSelected(position)}>{t('Ứng tuyển')}</Button>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </>
        )}
      </Container>
    </Box>
  );
}
