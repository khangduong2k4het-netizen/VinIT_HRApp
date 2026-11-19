'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress, Container, Divider,
  FormControlLabel, Grid, IconButton, InputAdornment, Stack, TextField, Typography, useMediaQuery, useTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import CloseIcon from '@mui/icons-material/Close';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import LocationOnOutlinedIcon from '@mui/icons-material/LocationOnOutlined';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import { useI18n } from '@/i18n/I18nProvider';
import LanguageSwitcher from '@/i18n/LanguageSwitcher';
import CollapsibleText from '@/components/public/CollapsibleText';
import {
  buildWithdrawalReceiptText, fetchPublicPositionDetail, fetchPublicPositions, filterPublicPositions,
  submitApplication, validateCv, type ApplyFailure, type PublicPosition, type PublicPositionDetail,
} from '@/lib/publicApply';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// Wording shown next to the tick box (notice v2, approved by Legal).
// When it changes, bump PUBLIC_INTAKE_NOTICE_VERSION on the backend.
export default function ApplyPage() {
  const { t } = useI18n();
  // Below the two-column layout the form sits under the whole job description, so the text is clamped there.
  const narrow = useMediaQuery(useTheme().breakpoints.down('lg'));
  const [positions, setPositions] = useState<PublicPosition[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [search, setSearch] = useState('');
  const [unitFilter, setUnitFilter] = useState('');
  const [selected, setSelected] = useState<PublicPosition | null>(null);
  const [detail, setDetail] = useState<PublicPositionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
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

  const units = useMemo(
    () => Array.from(new Set((positions || []).map(p => p.unit).filter((u): u is string => Boolean(u)))).sort(),
    [positions],
  );
  const visiblePositions = useMemo(
    () => filterPublicPositions(positions || [], { query: search, unit: unitFilter }),
    [positions, search, unitFilter],
  );

  const handleFilePick = (picked: File | null) => {
    setFile(picked);
    setFieldError(null);
    setFailure(null);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const dropped = event.dataTransfer.files?.[0] || null;
    if (dropped) handleFilePick(dropped);
  };

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
    <Box sx={{ minHeight: '100vh', bgcolor: '#F6F8FB', display: 'flex', flexDirection: 'column' }}>
      {/* Clean Academic Light top brand bar */}
      <Box
        component="header"
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 20,
          bgcolor: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(10px)',
          borderBottom: '1px solid #E5EAF0',
        }}
      >
        <Container maxWidth="lg" sx={{ height: 60, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/vinuni-logo.png" alt="VinUniversity" height={30} style={{ display: 'block' }} />
            <Divider orientation="vertical" flexItem sx={{ my: 1.5, display: { xs: 'none', sm: 'block' } }} />
            <Typography component="span" sx={{ fontWeight: 700, fontSize: 14, color: '#0A2B57', display: { xs: 'none', sm: 'inline' } }}>
              {t('Cơ hội nghề nghiệp tại VinUni')}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button component={Link} href="/apply/withdraw" size="small" color="inherit" sx={{ color: '#475569', display: { xs: 'none', sm: 'inline-flex' } }}>
              {t('Rút lại đồng ý Talent Pool')}
            </Button>
            <LanguageSwitcher />
          </Stack>
        </Container>
      </Box>

      {/* Editorial hero banner (shown on position listing) */}
      {!selected && !done && (
        <Box
          sx={{
            background: 'linear-gradient(135deg, #0A2B57 0%, #134D8B 100%)',
            color: '#FFFFFF',
            borderBottom: '3px solid #C72127',
            py: { xs: 4, md: 5.5 },
          }}
        >
          <Container maxWidth="lg">
            <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.75)', letterSpacing: '0.1em' }}>
              VinUniversity Careers
            </Typography>
            <Typography component="h1" sx={{ fontSize: { xs: 26, md: 34 }, fontWeight: 700, letterSpacing: '-0.02em', mt: 0.75 }}>
              {t('Vị trí đang tuyển')}
            </Typography>
            <Typography sx={{ color: 'rgba(255,255,255,0.82)', mt: 1, maxWidth: 640, fontSize: 15 }}>
              {t('Khám phá các cơ hội nghề nghiệp đang mở tại VinUniversity và nộp hồ sơ trực tuyến nhanh chóng.')}
            </Typography>
          </Container>
        </Box>
      )}

      <Container maxWidth="lg" sx={{ py: { xs: 3, md: 4.5 }, flexGrow: 1 }}>
        {done ? (
          <Card sx={{ maxWidth: 680, mx: 'auto', overflow: 'hidden' }}>
            <Box sx={{ height: 4, bgcolor: '#067647' }} />
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Stack spacing={2.5}>
                <Stack direction="row" spacing={1.5} alignItems="center" role="status">
                  <CheckCircleOutlineIcon sx={{ fontSize: 34, color: '#067647' }} />
                  <Box>
                    <Typography variant="h2" sx={{ color: '#0F172A' }}>{t('Đã nhận hồ sơ của bạn.')}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t('Bộ phận Nhân sự sẽ xem xét hồ sơ và liên hệ nếu phù hợp.')}
                    </Typography>
                  </Box>
                </Stack>
                {withdrawalToken && (
                  <Box sx={{ p: 2, bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px' }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: '#0F172A' }}>
                      {t('Mã để rút lại đồng ý dùng hồ sơ cho các vị trí khác. Hãy lưu mã này, hệ thống chỉ hiển thị một lần:')}
                    </Typography>
                    <Typography
                      component="code"
                      className="mono-code"
                      sx={{
                        display: 'block',
                        wordBreak: 'break-all',
                        fontSize: 12.5,
                        mt: 1,
                        p: 1.25,
                        bgcolor: '#FFFFFF',
                        border: '1px solid #CBD5E1',
                        borderRadius: '8px',
                        color: '#0A2B57',
                      }}
                    >
                      {withdrawalToken}
                    </Typography>
                    <Stack direction="row" spacing={1.25} alignItems="center" sx={{ mt: 1.5 }} flexWrap="wrap" useFlexGap>
                      <Button size="small" variant="contained" onClick={copyToken}>
                        {copiedToken ? t('Đã sao chép mã') : t('Sao chép mã')}
                      </Button>
                      <Button size="small" variant="outlined" onClick={downloadReceipt}>
                        {t('Tải biên nhận (.txt)')}
                      </Button>
                      <Typography variant="caption" color="text.secondary">
                        {t('Rút lại đồng ý tại')}{' '}
                        <Link href="/apply/withdraw" style={{ color: '#0A2B57', fontWeight: 600 }}>/apply/withdraw</Link>
                      </Typography>
                    </Stack>
                  </Box>
                )}
                <Box>
                  <Button variant="outlined" onClick={resetForAnother}>{t('Ứng tuyển vị trí khác')}</Button>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        ) : selected ? (
          <Box>
            <Button
              size="small"
              startIcon={<ArrowBackIcon fontSize="small" />}
              onClick={() => { setSelected(null); setFailure(null); setFieldError(null); }}
              sx={{ mb: 2, color: '#475569' }}
            >
              {t('Quay lại danh sách vị trí')}
            </Button>

            {/* 2-Column Editorial Job Detail + Sticky Apply Card */}
            <Grid container spacing={3} alignItems="flex-start">
              <Grid item xs={12} lg={7.5}>
                <Card>
                  <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
                      <Chip size="small" label={selected.code} className="mono-code" sx={{ bgcolor: '#EEF4FC', color: '#0A2B57', border: '1px solid #C7DDF7' }} />
                      {selected.employment_type && <Chip size="small" label={selected.employment_type} variant="outlined" />}
                      {detail?.level && <Chip size="small" label={detail.level} variant="outlined" />}
                      {detail?.work_mode && <Chip size="small" label={detail.work_mode} variant="outlined" />}
                    </Stack>
                    <Typography component="h1" variant="h1" sx={{ color: '#0F172A' }}>{selected.title}</Typography>
                    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mt: 1, color: '#475569' }}>
                      {selected.unit && (
                        <Stack direction="row" spacing={0.5} alignItems="center">
                          <BusinessOutlinedIcon sx={{ fontSize: 16, color: '#64748B' }} />
                          <Typography variant="body2">{selected.unit}</Typography>
                        </Stack>
                      )}
                      {selected.location && (
                        <Stack direction="row" spacing={0.5} alignItems="center">
                          <LocationOnOutlinedIcon sx={{ fontSize: 16, color: '#64748B' }} />
                          <Typography variant="body2">{selected.location}</Typography>
                        </Stack>
                      )}
                    </Stack>

                    {narrow && (
                      <Button
                        variant="contained"
                        fullWidth
                        sx={{ mt: 2, minHeight: 44 }}
                        onClick={() => document.getElementById('apply-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                      >
                        {t('Nộp hồ sơ ngay')}
                      </Button>
                    )}

                    <Divider sx={{ my: 2.5 }} />

                    {detailLoading && <CircularProgress size={22} aria-label={t('Đang tải')} />}

                    {detail?.posting_content && (
                      <Box sx={{ mb: 3 }}>
                        <Typography variant="h3" sx={{ color: '#0A2B57', mb: 1 }}>{t('Thông tin tuyển dụng')}</Typography>
                        <CollapsibleText enabled={narrow}>
                          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', color: '#1E293B', lineHeight: 1.7 }}>
                            {detail.posting_content}
                          </Typography>
                        </CollapsibleText>
                      </Box>
                    )}

                    {detail?.jd && (
                      <Box>
                        {detail?.posting_content && <Divider sx={{ my: 2.5 }} />}
                        <Typography variant="h3" sx={{ color: '#0A2B57', mb: 1 }}>{t('Mô tả công việc')}</Typography>
                        <CollapsibleText enabled={narrow}>
                          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', color: '#334155', lineHeight: 1.75 }}>
                            {detail.jd}
                          </Typography>
                        </CollapsibleText>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} lg={4.5} sx={{ position: { lg: 'sticky' }, top: { lg: 80 } }}>
                <Card component="form" id="apply-form" onSubmit={submit} noValidate sx={{ overflow: 'hidden', scrollMarginTop: 76 }}>
                  <Box sx={{ height: 3.5, bgcolor: '#C72127' }} />
                  <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
                    <Typography variant="h3" sx={{ color: '#0F172A', mb: 0.5 }}>{t('Nộp hồ sơ ứng tuyển')}</Typography>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                      {t('PDF, DOCX, JPG hoặc PNG, tối đa 10 MB.')}
                    </Typography>

                    <Stack spacing={2}>
                      {/* Drag-and-drop CV upload zone */}
                      {file ? (
                        <Box
                          sx={{
                            p: 1.5,
                            borderRadius: '10px',
                            border: '1px solid #C7DDF7',
                            bgcolor: '#EEF4FC',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 1,
                          }}
                        >
                          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ minWidth: 0 }}>
                            <InsertDriveFileOutlinedIcon sx={{ color: '#0A2B57', flexShrink: 0 }} />
                            <Box sx={{ minWidth: 0 }}>
                              <Typography variant="body2" noWrap sx={{ fontWeight: 600, color: '#0A2B57' }}>{file.name}</Typography>
                              <Typography variant="caption" color="text.secondary" className="tabular-nums">
                                {formatBytes(file.size)}
                              </Typography>
                            </Box>
                          </Stack>
                          <IconButton size="small" onClick={() => handleFilePick(null)} aria-label={t('Xóa tệp đã chọn')}>
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        </Box>
                      ) : (
                        <Box
                          component="label"
                          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                          onDragLeave={() => setDragOver(false)}
                          onDrop={handleDrop}
                          sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            textAlign: 'center',
                            py: 3.25,
                            px: 2,
                            borderRadius: '10px',
                            border: '1.5px dashed',
                            borderColor: dragOver ? '#0A2B57' : '#CBD5E1',
                            bgcolor: dragOver ? '#EEF4FC' : '#F8FAFC',
                            cursor: 'pointer',
                            transition: 'border-color 0.15s ease, background-color 0.15s ease',
                            '&:hover': { borderColor: '#0A2B57', bgcolor: '#F1F5FA' },
                          }}
                        >
                          <CloudUploadOutlinedIcon sx={{ fontSize: 32, color: '#0A2B57', mb: 0.75 }} />
                          <Typography variant="body2" sx={{ fontWeight: 600, color: '#0F172A' }}>
                            {t('Kéo thả CV vào đây hoặc bấm để chọn tệp')}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.25 }}>
                            PDF, DOCX, JPG, PNG · Max 10 MB
                          </Typography>
                          <input
                            type="file"
                            hidden
                            accept=".pdf,.docx,.jpg,.jpeg,.png"
                            onChange={e => handleFilePick(e.target.files?.[0] || null)}
                          />
                        </Box>
                      )}

                      <Box sx={{ p: 1.5, bgcolor: '#F8FAFC', borderRadius: '10px', border: '1px solid #E5EAF0' }}>
                        <FormControlLabel
                          required
                          sx={{ alignItems: 'flex-start', m: 0 }}
                          control={
                            <Checkbox
                              size="small"
                              sx={{ pt: 0.25, pr: 1 }}
                              checked={consentProcessing}
                              onChange={e => { setConsentProcessing(e.target.checked); setFieldError(null); }}
                            />
                          }
                          label={
                            <Typography variant="caption" sx={{ color: '#1E293B', lineHeight: 1.55, display: 'block' }}>
                              {t('Tôi đồng ý cho VinUniversity sử dụng thông tin trong hồ sơ này, bao gồm xử lý bằng công cụ AI, để xem xét ứng tuyển vào vị trí trên và các vị trí phù hợp khác. Hồ sơ được lưu tối đa 5 năm. Đây là điều kiện bắt buộc để nộp hồ sơ.')}
                            </Typography>
                          }
                        />
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, pl: 3.5, lineHeight: 1.45 }}>
                          {t('Sau khi nộp, bạn nhận một mã để rút lại đồng ý dùng hồ sơ cho các vị trí khác; bạn cũng có thể liên hệ bộ phận Nhân sự. Hồ sơ không được dùng cho mục đích khác ngoài tuyển dụng.')}
                        </Typography>
                      </Box>

                      {/* Honeypot: invisible to people and assistive technology; bots fill it in. */}
                      <Box aria-hidden="true" sx={{ position: 'absolute', left: '-10000px', width: 1, height: 1, overflow: 'hidden' }}>
                        <label>Website<input tabIndex={-1} autoComplete="off" value={honeypot} onChange={e => setHoneypot(e.target.value)} /></label>
                      </Box>

                      {fieldMessage && <Alert severity="error" role="alert">{fieldMessage}</Alert>}
                      {failureMessage && <Alert severity="error" role="alert">{failureMessage}</Alert>}

                      <Button
                        type="submit"
                        variant="contained"
                        color="secondary"
                        size="large"
                        fullWidth
                        disabled={busy}
                      >
                        {busy ? <CircularProgress size={20} color="inherit" aria-label={t('Đang gửi')} /> : t('Gửi hồ sơ')}
                      </Button>
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        ) : (
          <Stack spacing={2.5}>
            {/* Search & unit filters */}
            {positions && positions.length > 0 && (
              <Card>
                <CardContent sx={{ py: 2 }}>
                  <Stack spacing={1.5}>
                    <TextField
                      fullWidth
                      size="small"
                      placeholder={t('Tìm theo tên vị trí, mã tuyển dụng, đơn vị hoặc địa điểm...')}
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      InputProps={{
                        startAdornment: (
                          <InputAdornment position="start">
                            <SearchIcon fontSize="small" sx={{ color: '#64748B' }} />
                          </InputAdornment>
                        ),
                      }}
                    />
                    {units.length > 1 && (
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Chip
                          size="small"
                          label={t('Tất cả')}
                          color={unitFilter === '' ? 'primary' : 'default'}
                          variant={unitFilter === '' ? 'filled' : 'outlined'}
                          onClick={() => setUnitFilter('')}
                        />
                        {units.map(unit => (
                          <Chip
                            key={unit}
                            size="small"
                            label={unit}
                            color={unitFilter === unit ? 'primary' : 'default'}
                            variant={unitFilter === unit ? 'filled' : 'outlined'}
                            onClick={() => setUnitFilter(unit)}
                          />
                        ))}
                      </Stack>
                    )}
                  </Stack>
                </CardContent>
              </Card>
            )}

            {positions === null && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                <CircularProgress aria-label={t('Đang tải')} />
              </Box>
            )}
            {loadError && (
              <Alert severity="error" action={<Button color="inherit" onClick={load}>{t('Thử lại')}</Button>}>
                {t('Không thể tải danh sách vị trí.')}
              </Alert>
            )}
            {positions && !loadError && positions.length === 0 && (
              <Alert severity="info">{t('Hiện chưa có vị trí nào đang nhận hồ sơ.')}</Alert>
            )}
            {positions && !loadError && positions.length > 0 && visiblePositions.length === 0 && (
              <Alert severity="info">{t('Không tìm thấy vị trí phù hợp với bộ lọc hiện tại.')}</Alert>
            )}

            <Grid container spacing={2}>
              {visiblePositions.map(position => (
                <Grid item xs={12} md={6} key={position.code}>
                  <Card
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      '&:hover': {
                        borderColor: '#0A2B57',
                        boxShadow: '0 8px 22px rgba(10, 43, 87, 0.08)',
                      },
                    }}
                  >
                    <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 2 }}>
                      <Box>
                        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                          <Chip
                            size="small"
                            label={position.code}
                            className="mono-code"
                            sx={{ bgcolor: '#EEF4FC', color: '#0A2B57', border: '1px solid #C7DDF7', fontSize: 11 }}
                          />
                          {position.employment_type && (
                            <Stack direction="row" spacing={0.5} alignItems="center" sx={{ color: '#64748B' }}>
                              <WorkOutlineIcon sx={{ fontSize: 14 }} />
                              <Typography variant="caption">{position.employment_type}</Typography>
                            </Stack>
                          )}
                        </Stack>
                        <Typography variant="h3" sx={{ color: '#0F172A', mb: 0.75 }}>{position.title}</Typography>
                        <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ color: '#64748B' }}>
                          {position.unit && (
                            <Stack direction="row" spacing={0.5} alignItems="center">
                              <BusinessOutlinedIcon sx={{ fontSize: 15 }} />
                              <Typography variant="caption">{position.unit}</Typography>
                            </Stack>
                          )}
                          {position.location && (
                            <Stack direction="row" spacing={0.5} alignItems="center">
                              <LocationOnOutlinedIcon sx={{ fontSize: 15 }} />
                              <Typography variant="caption">{position.location}</Typography>
                            </Stack>
                          )}
                        </Stack>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <Button
                          variant="contained"
                          endIcon={<ArrowForwardIcon fontSize="small" />}
                          onClick={() => setSelected(position)}
                        >
                          {t('Ứng tuyển')}
                        </Button>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Stack>
        )}
      </Container>

      <Box component="footer" sx={{ borderTop: '1px solid #E5EAF0', bgcolor: '#FFFFFF', py: 2.5, mt: 'auto' }}>
        <Container maxWidth="lg" sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="caption" color="text.secondary">© {new Date().getFullYear()} VinUniversity Careers</Typography>
          <Link href="/apply/withdraw" style={{ fontSize: 12, color: '#0A2B57', fontWeight: 600, textDecoration: 'none' }}>
            {t('Rút lại đồng ý Talent Pool')}
          </Link>
        </Container>
      </Box>
    </Box>
  );
}
