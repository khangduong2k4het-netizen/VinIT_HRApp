'use client';

import * as React from 'react';
import { useState } from 'react';
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, CircularProgress,
  Divider, FormControlLabel, Stack, Table, TableBody, TableCell, TableHead, TableRow,
  TextField, Typography,
} from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { testDataApi } from '@/lib/api';

/**
 * Dọn dữ liệu test — dùng trong lúc phát triển, không phải nghiệp vụ HR.
 *
 * Ba quyết định về UX, mỗi cái vì một cách hỏng đã gặp thật:
 *
 * 1. **Đếm trước khi xoá, bắt buộc.** Nút "Xoá" không bấm được trước khi ADMIN
 *    xem qua bảng số dòng sẽ mất. "Tôi tưởng chỉ xoá CV" là câu không được phép
 *    xảy ra với dữ liệu.
 * 2. **Gõ chuỗi xác nhận, không dùng checkbox.** Checkbox bấm theo quán tính, còn
 *    gõ đúng chuỗi thì phải đọc. Chuỗi hiện là "OK" và không phân biệt hoa/thường
 *    (người dùng chốt đổi từ "XOA DU LIEU TEST" cho đỡ vướng).
 * 3. **Nói rõ cái gì KHÔNG mất.** Câu hỏi đầu tiên của mọi người trước khi bấm
 *    nút xoá là "có mất tài khoản không". Trả lời trước khi họ phải hỏi.
 */

interface Scope {
  code: string;
  label: string;
  description: string;
  pulls_in: string[];
}

interface PreviewTable {
  name: string;
  rows: number;
}

interface Preview {
  requested_scopes: string[];
  effective_scopes: string[];
  implied_scopes: string[];
  /** Vì sao phạm vi bị mở rộng; máy chủ soạn để không phải suy diễn ở UI. */
  scope_note?: string | null;
  tables: PreviewTable[];
  total_rows: number;
  storage: {
    buckets: { bucket: string; documents: number }[];
    objects: number;
    note: string;
    orphans?: {
      supported: boolean;
      reason?: string;
      error?: string;
      total_orphans?: number;
      buckets?: { bucket: string; objects: number; orphans: number }[];
    };
  };
  protected: { table: string; rows: number }[];
}

interface PurgeResult {
  effective_scopes: string[];
  rows_deleted: Record<string, number>;
  rows_total: number;
  skipped_tables: string[];
  storage: {
    skipped?: boolean;
    error?: boolean;
    storage_objects_deleted?: number;
    storage_objects_missing?: number;
    sweep?: { swept: boolean; deleted?: number; kept_fresh?: number; reason?: string };
  };
  storage_error: string | null;
}

export default function TestDataPurge() {
  const { t } = useI18n();
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [phrase, setPhrase] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [typed, setTyped] = useState('');
  const [result, setResult] = useState<PurgeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingScopes, setLoadingScopes] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [running, setRunning] = useState(false);

  const load = React.useCallback(async () => {
    try {
      setLoadingScopes(true); setError(null);
      const response = await testDataApi.getScopes();
      setScopes(response.data.scopes);
      setPhrase(response.data.confirmation_phrase);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không tải được danh sách nhóm dữ liệu.'));
    } finally {
      setLoadingScopes(false);
    }
  }, [t]);

  React.useEffect(() => { load(); }, [load]);

  const toggle = (code: string) => {
    setSelected(previous => previous.includes(code) ? previous.filter(c => c !== code) : [...previous, code]);
    // Preview cũ không còn đúng khi phạm vi đổi — bỏ đi thay vì để ADMIN đọc số cũ.
    setPreview(null);
    setTyped('');
    setResult(null);
  };

  const runPreview = async () => {
    try {
      setPreviewing(true); setError(null); setResult(null);
      const response = await testDataApi.preview(selected);
      setPreview(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không đếm được dữ liệu.'));
    } finally {
      setPreviewing(false);
    }
  };

  const runPurge = async () => {
    try {
      setRunning(true); setError(null);
      const response = await testDataApi.execute(selected, typed);
      setResult(response.data);
      setPreview(null);
      setTyped('');
    } catch (err: any) {
      setError(err.response?.data?.detail || t('Không xoá được dữ liệu.'));
    } finally {
      setRunning(false);
    }
  };

  // So khớp y như backend: bỏ khoảng trắng hai đầu và không phân biệt hoa/thường.
  // Hai bên phải cùng quy tắc, nếu không sẽ có cảnh gõ đúng mà nút vẫn xám.
  const confirmMatches = typed.trim().toUpperCase() === phrase.trim().toUpperCase();
  const impliedLabels = (preview?.implied_scopes || [])
    .map(code => scopes.find(s => s.code === code)?.label || code);

  if (loadingScopes) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress color="secondary" /></Box>;
  }

  return (
    <Box data-testid="test-data-purge">
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      <Alert severity="warning" sx={{ mb: 3 }}>
        <Typography fontWeight={700} sx={{ mb: 0.5 }}>
          {t('Công cụ dành cho môi trường phát triển và kiểm thử')}
        </Typography>
        <Typography variant="body2">
          {t('Thao tác này xoá dữ liệu vĩnh viễn và không hoàn tác được. Dùng để dọn dữ liệu giả trước khi chạy lại luồng demo. Không dùng trên môi trường có dữ liệu ứng viên thật.')}
        </Typography>
      </Alert>

      <Card variant="outlined" sx={{ borderColor: '#E4EAF2', mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={700} color="#0A2B57" sx={{ mb: 0.5 }}>
            {t('Bước 1 — Chọn nhóm dữ liệu cần xoá')}
          </Typography>
          <Stack spacing={0.5}>
            {scopes.map(scope => (
              <Box key={scope.code}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={selected.includes(scope.code)}
                      onChange={() => toggle(scope.code)}
                      inputProps={{ 'aria-label': scope.label }}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={600}>{t(scope.label)}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                        {t(scope.description)}
                      </Typography>
                      {scope.pulls_in.length > 0 && (
                        <Typography variant="caption" sx={{ display: 'block', color: '#B54708', mt: 0.25 }}>
                          {t('Kéo theo: {0}', scope.pulls_in.map(c => scopes.find(s => s.code === c)?.label || c).join(', '))}
                        </Typography>
                      )}
                    </Box>
                  }
                  sx={{ alignItems: 'flex-start', mb: 1 }}
                />
              </Box>
            ))}
          </Stack>

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle1" fontWeight={700} color="#0A2B57" sx={{ mb: 0.5 }}>
            {t('Bước 2 — Xem trước sẽ mất gì')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('Chưa có gì bị xoá ở bước này.')}
          </Typography>

          <Button
            variant="outlined"
            onClick={runPreview}
            disabled={selected.length === 0 || previewing}
            data-testid="purge-preview-button"
          >
            {previewing ? t('Đang đếm...') : t('Đếm dữ liệu sẽ xoá')}
          </Button>

          {preview && (
            <Box sx={{ mt: 2 }} aria-live="polite">
              {impliedLabels.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }} data-testid="purge-scope-widened">
                  <Typography fontWeight={700} sx={{ mb: 0.5 }}>
                    {t('Phạm vi xoá rộng hơn những gì bạn chọn: {0}', impliedLabels.join(', '))}
                  </Typography>
                  {/* Máy chủ soạn câu giải thích vì nó biết ràng buộc khoá ngoại;
                      UI không tự diễn giải lại để hai bên không lệch nhau. */}
                  {preview.scope_note && <Typography variant="body2">{t(preview.scope_note)}</Typography>}
                </Alert>
              )}

              <Typography variant="body2" sx={{ mb: 1 }}>
                {t('Tổng cộng {0} dòng trong {1} bảng sẽ bị xoá.', String(preview.total_rows),
                   String(preview.tables.filter(x => x.rows > 0).length))}
              </Typography>

              <Table size="small" data-testid="purge-preview-table">
                <TableHead>
                  <TableRow>
                    <TableCell>{t('Bảng')}</TableCell>
                    <TableCell align="right">{t('Số dòng')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.tables.filter(row => row.rows > 0).map(row => (
                    <TableRow key={row.name}>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 13 }}>{row.name}</TableCell>
                      <TableCell align="right">{row.rows}</TableCell>
                    </TableRow>
                  ))}
                  {preview.tables.every(row => row.rows === 0) && (
                    <TableRow>
                      <TableCell colSpan={2}>
                        <Typography variant="body2" color="text.secondary">
                          {t('Không có dòng nào trong phạm vi này — chưa có gì để xoá.')}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {preview.storage.objects > 0 && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  {t('Kèm {0} tài liệu trong Storage. {1}', String(preview.storage.objects), preview.storage.note)}
                </Typography>
              )}

              {(() => {
                const orphans = preview.storage.orphans;
                if (!orphans) return null;
                if (!orphans.supported) {
                  return (
                    <Alert severity="info" sx={{ mt: 1.5 }} data-testid="purge-orphans-unsupported">
                      {t('Không đối soát được Storage ({0}) — file CV sẽ không được dọn tự động.', orphans.reason || '')}
                    </Alert>
                  );
                }
                if (orphans.error) {
                  return (
                    <Alert severity="warning" sx={{ mt: 1.5 }} data-testid="purge-orphans-error">
                      {t('Không liệt kê được file trên Storage: {0}. Thao tác xoá vẫn chạy, nhưng sẽ không dọn được file mồ côi.', orphans.error)}
                    </Alert>
                  );
                }
                const total = orphans.total_orphans || 0;
                return (
                  <Alert severity={total > 0 ? 'warning' : 'success'} sx={{ mt: 1.5 }} data-testid="purge-orphans">
                    {total > 0
                      ? t('Có {0} file mồ côi trên Storage (DB không còn trỏ tới — thường do lần xoá trước). Chúng sẽ được dọn cùng lần này.', String(total))
                      : t('Storage không có file mồ côi.')}
                    {(orphans.buckets || []).length > 0 && (
                      <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                        {(orphans.buckets || []).map(b => `${b.bucket}: ${b.orphans}/${b.objects}`).join(' · ')}
                      </Typography>
                    )}
                  </Alert>
                );
              })()}

              <Box sx={{ mt: 2, p: 1.5, backgroundColor: '#F5F8FC', borderRadius: 1 }}>
                <Typography variant="body2" fontWeight={600} sx={{ mb: 0.5 }}>
                  {t('Những thứ KHÔNG bị xoá:')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {preview.protected.map(p => `${p.table} (${p.rows})`).join(' · ')}
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', color: '#067647', mt: 0.5 }}>
                  {t('Tài khoản, phòng ban, cấu hình AI và cấu hình ngưỡng được giữ nguyên.')}
                </Typography>
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      <Card variant="outlined" sx={{ borderColor: '#FDA29B' }}>
        <CardContent>
          <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#B42318', mb: 0.5 }}>
            {t('Bước 3 — Xác nhận và xoá')}
          </Typography>

          {!preview && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('Phải xem trước ở bước 2 thì nút xoá mới bật.')}
            </Typography>
          )}

          <Typography variant="body2" sx={{ mb: 1 }}>
            {t('Gõ chính xác chuỗi sau để bật nút xoá:')}
            <Box component="code" sx={{ ml: 1, px: 1, py: 0.25, backgroundColor: '#F3F5F8', borderRadius: 0.5, fontWeight: 700 }}>
              {phrase}
            </Box>
          </Typography>
          <TextField
            size="small"
            fullWidth
            value={typed}
            onChange={event => setTyped(event.target.value)}
            placeholder={phrase}
            disabled={!preview || running}
            inputProps={{ 'aria-label': t('Chuỗi xác nhận'), autoComplete: 'off', spellCheck: false }}
            sx={{ mb: 2, maxWidth: 360 }}
            data-testid="purge-confirm-input"
          />

          <Button
            variant="contained"
            color="error"
            onClick={runPurge}
            disabled={!preview || !confirmMatches || running}
            data-testid="purge-execute-button"
          >
            {running ? t('Đang xoá...') : t('Xoá dữ liệu đã chọn')}
          </Button>

          {preview && !confirmMatches && typed.length > 0 && (
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: '#B42318' }}>
              {t('Chuỗi chưa khớp — gõ đúng {0}.', phrase)}
            </Typography>
          )}
        </CardContent>
      </Card>

      {result && (
        <Card variant="outlined" sx={{ borderColor: '#ABEFC6', mt: 2 }} data-testid="purge-result">
          <CardContent>
            <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#067647', mb: 1 }}>
              {t('Đã xoá {0} dòng.', String(result.rows_total))}
            </Typography>

            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1.5 }}>
              {result.effective_scopes.map(code => (
                <Chip key={code} size="small" label={scopes.find(s => s.code === code)?.label || code} />
              ))}
            </Box>

            {result.storage_error ? (
              <Alert severity="warning" sx={{ mt: 1 }}>
                {t('Dữ liệu trong DB đã xoá xong, nhưng file CV trên Storage chưa xoá được: {0}', result.storage_error)}
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                  {t('File còn lại không hiện trong ứng dụng nhưng vẫn chiếm chỗ. Xoá thủ công trong Supabase → Storage.')}
                </Typography>
              </Alert>
            ) : (result.storage.sweep?.swept ?? false) ? (
              <Alert severity="success">
                {t('Đã dọn {0} file mồ côi trên Storage.', String(result.storage.sweep?.deleted ?? 0))}
                {(result.storage.sweep?.kept_fresh ?? 0) > 0 &&
                  ` ${t('Giữ lại {0} file vừa tạo trong 15 phút qua — có thể đang được tải lên.', String(result.storage.sweep?.kept_fresh ?? 0))}`}
              </Alert>
            ) : (
              <Alert severity="info">{t('Phạm vi này không bao gồm file trên Storage.')}</Alert>
            )}

            {result.skipped_tables.length > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {t('Bỏ qua {0} bảng chưa tồn tại trong DB này.', String(result.skipped_tables.length))}
              </Typography>
            )}

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
              {t('Đã ghi vào nhật ký kiểm toán. Vị trí mới sẽ bắt đầu lại từ mã 0001.')}
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
