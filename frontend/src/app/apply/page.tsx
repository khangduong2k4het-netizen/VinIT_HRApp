'use client';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Checkbox, CircularProgress, Container, FormControlLabel, Stack, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import { fetchPublicPositions, submitApplication, validateCv, type ApplyFailure, type PublicPosition } from '@/lib/publicApply';

// Wording version is CONSENT_NOTICE_VERSION in lib/publicApply.ts. When it
// changes, update that constant and backend PUBLIC_INTAKE_NOTICE_VERSION together.
export default function ApplyPage() {
  const { t } = useI18n();
  const [positions, setPositions] = useState<PublicPosition[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<PublicPosition | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [consentProcessing, setConsentProcessing] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [fieldError, setFieldError] = useState<'MISSING' | 'TYPE' | 'SIZE' | 'CONSENT' | null>(null);
  const [failure, setFailure] = useState<ApplyFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [withdrawalToken, setWithdrawalToken] = useState<string | null>(null);

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
    const result = await submitApplication(selected.code, file as File, consentProcessing, honeypot);
    setBusy(false);
    if (result.ok) { setWithdrawalToken(result.withdrawalToken ?? null); setDone(true); } else setFailure(result.failure);
  };

  const fieldMessage = fieldError === 'MISSING' ? t('Vui lòng chọn tệp CV.')
    : fieldError === 'TYPE' ? t('Chỉ hỗ trợ tệp PDF, DOCX, JPG hoặc PNG.')
    : fieldError === 'SIZE' ? t('Tệp phải có nội dung và không vượt quá 10 MB.')
    : fieldError === 'CONSENT' ? t('Cần đồng ý cho phép sử dụng thông tin hồ sơ để ứng tuyển.') : '';
  const failureMessage = failure === 'RATE_LIMIT' ? t('Bạn đã gửi quá nhiều lần. Vui lòng thử lại sau.')
    : failure === 'UNAVAILABLE' ? t('Hệ thống tạm thời chưa nhận hồ sơ. Vui lòng thử lại sau.')
    : failure === 'POSITION_CLOSED' ? t('Vị trí không còn nhận hồ sơ.')
    : failure === 'NOTICE_CHANGED' ? t('Nội dung đồng ý đã thay đổi. Vui lòng tải lại trang trước khi nộp hồ sơ.')
    : failure === 'CONSENT' ? t('Cần đồng ý cho phép sử dụng thông tin hồ sơ để ứng tuyển.')
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
            {withdrawalToken && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2">{t('Mã để rút lại đồng ý dùng hồ sơ cho các vị trí khác. Hãy lưu mã này, hệ thống chỉ hiển thị một lần:')}</Typography>
                <Typography component="code" sx={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', mt: 0.5 }}>{withdrawalToken}</Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>{t('Rút lại đồng ý tại')} <a href="/apply/withdraw">/apply/withdraw</a></Typography>
              </Box>
            )}
          </Alert>
        ) : selected ? (
          <Card component="form" onSubmit={submit} noValidate>
            <CardContent>
              <Button size="small" disabled={busy} onClick={() => { setSelected(null); setFile(null); setConsentProcessing(false); setFailure(null); setFieldError(null); }}>{t('← Quay lại danh sách')}</Button>
              <Typography variant="h5" sx={{ fontWeight: 700, mt: 1 }}>{selected.title}</Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>{[selected.unit, selected.location].filter(Boolean).join(' · ')}</Typography>
              <Stack spacing={2}>
                <Box>
                  <Button variant="outlined" component="label">
                    {file ? file.name : t('Chọn tệp CV')}
                    <input type="file" hidden disabled={busy} accept=".pdf,.docx,.jpg,.jpeg,.png"
                      onChange={e => { setFile(e.target.files?.[0] || null); setFieldError(null); }} />
                  </Button>
                  <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>{t('PDF, DOCX, JPG hoặc PNG, tối đa 10 MB.')}</Typography>
                </Box>
                <FormControlLabel
                  required
                  control={<Checkbox disabled={busy} checked={consentProcessing} onChange={e => { setConsentProcessing(e.target.checked); setFieldError(null); }} />}
                  label={t('Tôi đồng ý cho VinUniversity xử lý hồ sơ, bao gồm hỗ trợ đánh giá bằng AI, để ứng tuyển vị trí này và tham gia Talent Pool cho các vị trí phù hợp khác. Hồ sơ được lưu tối đa 5 năm kể từ khi vị trí tuyển dụng đóng; quyền dùng lại trong Talent Pool có hiệu lực 5 năm từ ngày đồng ý.')} />
                <Typography variant="caption" color="text.secondary">
                  {t('Bạn cần đồng ý để nộp hồ sơ. Sau khi nộp, bạn nhận mã để rút lại đồng ý dùng hồ sơ cho vị trí khác; mã chỉ hiển thị một lần.')}
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
