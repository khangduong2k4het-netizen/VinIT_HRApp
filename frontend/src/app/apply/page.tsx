'use client';

import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress, Container, Divider, FormControlLabel, Stack, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import {
  buildWithdrawalReceiptText, fetchPublicPositionDetail, fetchPublicPositions, submitApplication, validateCv,
  type ApplyFailure, type PublicPosition, type PublicPositionDetail,
} from '@/lib/publicApply';

// Wording shown next to the tick box (notice v2, approved by Legal).
// When it changes, bump PUBLIC_INTAKE_NOTICE_VERSION on the backend.
export default function ApplyPage() {
  const { t } = useI18n();
  const [positions, setPositions] = useState<PublicPosition[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<PublicPosition | null>(null);
  const [detail, setDetail] = useState<PublicPositionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  // One mandatory consent (notice v2): use of the CV incl. AI, 5-year storage, reuse for other positions.
  const [consentProcessing, setConsentProcessing] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [fieldError, setFieldError] = useState<'MISSING' | 'TYPE' | 'SIZE' | 'CONSENT' | null>(null);
  const [failure, setFailure] = useState<ApplyFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [withdrawalToken, setWithdrawalToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const list = await fetchPublicPositions();
      setPositions(list);
      const code = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('code') : null;
      if (code) {
        const match = list.find(p => p.code.toLowerCase() === code.trim().toLowerCase());
        if (match) setSelected(match);
      }
    } catch { setPositions([]); setLoadError(true); }
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    let active = true;
    setDetailLoading(true);
    fetchPublicPositionDetail(selected.code)
      .then(d => { if (active) setDetail(d); })
      .catch(() => { if (active) setDetail(null); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selected]);

  const copyToken = async () => {
    if (!withdrawalToken) return;
    try {
      await navigator.clipboard.writeText(withdrawalToken);
      setCopiedToken(true);
      window.setTimeout(() => setCopiedToken(false), 2000);
    } catch {
      setCopiedToken(false);
    }
  };

  const downloadReceipt = () => {
    if (!withdrawalToken || !selected) return;
    const content = buildWithdrawalReceiptText(selected.code, selected.title, withdrawalToken, window.location.origin);
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vinuni-receipt-${selected.code}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetForAnother = () => {
    setDone(false);
    setSelected(null);
    setDetail(null);
    setFile(null);
    setConsentProcessing(false);
    setFieldError(null);
    setFailure(null);
    setWithdrawalToken(null);
    setCopiedToken(false);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected || busy) return;
    setFailure(null);
    const problem = validateCv(file);
    if (problem) { setFieldError(problem); return; }
    if (!consentProcessing) { setFieldError('CONSENT'); return; }
    setFieldError(null);
    setBusy(true);
    const result = await submitApplication(selected.code, file as File, true, honeypot);
    setBusy(false);
    if (result.ok) { setWithdrawalToken(result.withdrawalToken ?? null); setDone(true); } else setFailure(result.failure);
  };

  const fieldMessage = fieldError === 'MISSING' ? t('Vui lòng chọn tệp CV.')
    : fieldError === 'TYPE' ? t('Chỉ hỗ trợ tệp PDF, DOCX, JPG hoặc PNG.')
    : fieldError === 'SIZE' ? t('Tệp vượt quá 10 MB.')
    : fieldError === 'CONSENT' ? t('Cần đồng ý cho phép sử dụng thông tin hồ sơ để ứng tuyển.') : '';
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
          <Stack spacing={2}>
            <Alert severity="success" role="status">
              <Typography sx={{ fontWeight: 700 }}>{t('Đã nhận hồ sơ của bạn.')}</Typography>
              {t('Bộ phận Nhân sự sẽ xem xét hồ sơ và liên hệ nếu phù hợp.')}
              {withdrawalToken && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2">{t('Mã để rút lại đồng ý dùng hồ sơ cho các vị trí khác. Hãy lưu mã này, hệ thống chỉ hiển thị một lần:')}</Typography>
                  <Typography component="code" sx={{ display: 'block', wordBreak: 'break-all', fontFamily: 'monospace', mt: 0.5, p: 1, bgcolor: 'rgba(255,255,255,0.7)', borderRadius: 1 }}>{withdrawalToken}</Typography>
                  <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mt: 1 }} flexWrap="wrap">
                    <Button size="small" variant="outlined" onClick={copyToken}>
                      {copiedToken ? t('Đã sao chép mã') : t('Sao chép mã')}
                    </Button>
                    <Button size="small" variant="outlined" onClick={downloadReceipt}>
                      {t('Tải biên nhận (.txt)')}
                    </Button>
                    <Typography variant="body2">{t('Rút lại đồng ý tại')} <Link href="/apply/withdraw">/apply/withdraw</Link></Typography>
                  </Stack>
                </Box>
              )}
            </Alert>
            <Box>
              <Button variant="outlined" onClick={resetForAnother}>{t('Ứng tuyển vị trí khác')}</Button>
            </Box>
          </Stack>
        ) : selected ? (
          <Stack spacing={2.5}>
            <Card variant="outlined">
              <CardContent>
                <Button size="small" onClick={() => { setSelected(null); setFailure(null); setFieldError(null); }}>{t('← Quay lại danh sách')}</Button>
                <Typography variant="h5" sx={{ fontWeight: 700, mt: 1 }}>{selected.title}</Typography>
                <Typography color="text.secondary" sx={{ mb: 1.5 }}>{[selected.unit, selected.location].filter(Boolean).join(' · ')}</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
                  <Chip size="small" label={selected.code} variant="outlined" />
                  {selected.employment_type && <Chip size="small" label={selected.employment_type} />}
                  {detail?.level && <Chip size="small" label={detail.level} />}
                  {detail?.work_mode && <Chip size="small" label={detail.work_mode} />}
                </Stack>
                {detailLoading && <CircularProgress size={20} aria-label={t('Đang tải')} />}
                {detail?.posting_content && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>{t('Thông tin tuyển dụng')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{detail.posting_content}</Typography>
                  </Box>
                )}
                {detail?.jd && (
                  <Box>
                    {detail?.posting_content && <Divider sx={{ my: 2 }} />}
                    <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>{t('Mô tả công việc')}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', maxHeight: 360, overflowY: 'auto', pr: 1 }}>
                      {detail.jd}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
            <Card component="form" onSubmit={submit} noValidate>
              <CardContent>
                <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>{t('Nộp hồ sơ ứng tuyển')}</Typography>
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
                    required
                    control={<Checkbox checked={consentProcessing} onChange={e => { setConsentProcessing(e.target.checked); setFieldError(null); }} />}
                    label={t('Tôi đồng ý cho VinUniversity sử dụng thông tin trong hồ sơ này, bao gồm xử lý bằng công cụ AI, để xem xét ứng tuyển vào vị trí trên và các vị trí phù hợp khác. Hồ sơ được lưu tối đa 5 năm. Đây là điều kiện bắt buộc để nộp hồ sơ.')} />
                  <Typography variant="caption" color="text.secondary">
                    {t('Sau khi nộp, bạn nhận một mã để rút lại đồng ý dùng hồ sơ cho các vị trí khác; bạn cũng có thể liên hệ bộ phận Nhân sự. Hồ sơ không được dùng cho mục đích khác ngoài tuyển dụng.')}
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
          </Stack>
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
