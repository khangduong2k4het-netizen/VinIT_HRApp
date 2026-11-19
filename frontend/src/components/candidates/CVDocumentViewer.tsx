'use client';

import * as React from 'react';
import {
  Box, Button, Card, CardContent, CircularProgress, IconButton, Table, TableBody, TableCell,
  TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import { useI18n } from '@/i18n/I18nProvider';
import type { DocxBlock } from '@/lib/docxText';

interface CVDocumentViewerProps {
  cvUrl: string | null;
  cvError: string | null;
  isPdf: boolean;
  canViewCv: boolean;
  selectedPage: number;
  onPageChange: (page: number) => void;
  /** The file is fetched on demand, never just because the profile opened. */
  requested?: boolean;
  loading?: boolean;
  onRequest?: () => void;
  /**
   * Blocks read from a .docx in the browser, so HR can screen without downloading.
   * Tables stay tables: a CV with a table read as a flat paragraph stream puts each
   * cell on its own line and the reviewer compares the wrong row.
   */
  docxBlocks?: DocxBlock[] | null;
  docxError?: string | null;
}

export default function CVDocumentViewer({ cvUrl, cvError, isPdf, canViewCv, selectedPage, onPageChange, requested = true, loading = false, onRequest, docxBlocks = null, docxError = null }: CVDocumentViewerProps) {
  const { t } = useI18n();
  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" sx={{ fontSize: 16, fontWeight: 600, color: '#0A2B57' }}>{t("CV gốc")}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title={t("Trang trước")}>
            <span>
              <IconButton aria-label={t("Trang trước")} size="small" disabled={!cvUrl || !isPdf || selectedPage <= 1} onClick={() => onPageChange(selectedPage - 1)}>
                <NavigateBeforeIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="body2">{t("Trang")} {selectedPage}</Typography>
          <Tooltip title={t("Trang sau")}>
            <span>
              <IconButton aria-label={t("Trang sau")} size="small" disabled={!cvUrl || !isPdf} onClick={() => onPageChange(selectedPage + 1)}>
                <NavigateNextIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {/* Height is bounded by where the panel may sit, not by taste. The panel
          sticks at top:152 and the criteria column ends 777px down the viewport
          when the last criterion is on screen; the heading row (34px) plus this
          card must fit inside that 625px, or sticky pins the bottom to the
          container edge and pushes the title up under the queue bar (bar ends at
          143px). 400 = 152 + heading + grid padding, with enough slack that the title
          clears the bar at the last criterion instead of ducking under it. */}
      <Card sx={{ height: 'calc(100vh - 400px)', minHeight: 360, overflow: 'auto' }}>
        <CardContent sx={{ p: 0, height: '100%' }}>
          {cvUrl && isPdf ? (
            <Box sx={{ height: '100%', backgroundColor: '#525659', padding: 2 }}>
              <iframe id="cv-pdf-viewer" src={`${cvUrl}#page=${selectedPage}`} width="100%" height="100%" style={{ border: 'none', backgroundColor: 'white' }} title={t("CV gốc")} />
            </Box>
          ) : cvUrl && docxBlocks && docxBlocks.length > 0 ? (
            // A .docx cannot be shown as-is by the browser, and converting it on the
            // server would add a converter to the request path. Instead the file HR
            // already fetched is read here: the words are what screening needs, and
            // the original layout stays one click away.
            <Box sx={{ height: '100%', overflow: 'auto', backgroundColor: 'white' }} data-testid="docx-text">
              <Box sx={{ px: 3, py: 2, borderBottom: '1px solid #EDF1F5', position: 'sticky', top: 0, backgroundColor: 'white', zIndex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("Nội dung đọc từ tệp DOCX; bố cục gốc có thể khác. Tải CV gốc để xem đúng định dạng.")}
                </Typography>
              </Box>
              <Box sx={{ px: 3, py: 2.5, maxWidth: 760 }}>
                {docxBlocks.map((block, index) => block.kind === 'paragraph' ? (
                  block.text === '' ? (
                    <Box key={index} sx={{ height: 10 }} />
                  ) : (
                    <Typography
                      key={index}
                      component="p"
                      sx={{ fontSize: 14, lineHeight: 1.7, color: '#1D2939', mb: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
                    >
                      {block.text}
                    </Typography>
                  )
                ) : (
                  // A table in the CV stays a table. Rows and cells are read in document
                  // order, so "Python | 2022 | VinIT" cannot drift onto three lines.
                  <Box key={index} sx={{ mb: 1.5, maxWidth: '100%', overflowX: 'auto' }} data-testid="docx-table">
                    <Table size="small" sx={{ border: '1px solid #D0D5DD', '& td, & th': { border: '1px solid #EAECF0', verticalAlign: 'top', fontSize: 13, lineHeight: 1.5, color: '#1D2939' } }}>
                      {block.header && block.rows.length > 1 ? (
                        <TableHead>
                          <TableRow>
                            {block.rows[0].map((cell, column) => (
                              <TableCell key={column} sx={{ fontWeight: 700, backgroundColor: '#F9FAFB' }}>{cell}</TableCell>
                            ))}
                          </TableRow>
                        </TableHead>
                      ) : null}
                      <TableBody>
                        {(block.header && block.rows.length > 1 ? block.rows.slice(1) : block.rows).map((row, rowIndex) => (
                          <TableRow key={rowIndex}>
                            {row.map((cell, column) => <TableCell key={column}>{cell}</TableCell>)}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Box>
                ))}
              </Box>
            </Box>
          ) : cvUrl && !isPdf && docxError ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{t(docxError)}</Typography>
            </Box>
          ) : !canViewCv ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{t("Shortlist này không cho phép xem CV gốc.")}</Typography>
            </Box>
          ) : !requested ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 1.5, height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{t("CV gốc chưa được tải. Bằng chứng AI bên trái đọc được mà không cần mở tệp.")}</Typography>
              <Button variant="outlined" startIcon={<VisibilityIcon />} onClick={onRequest} disabled={!onRequest}>{t("Xem CV gốc")}</Button>
              <Typography variant="caption">{t("Tệp được tải và ghi nhận truy cập khi bạn bấm, không tự tải khi mở hồ sơ.")}</Typography>
            </Box>
          ) : loading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 1.5, p: 3 }}>
              <CircularProgress size={20} /><Typography variant="body2" color="text.secondary">{t("Đang tải CV…")}</Typography>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', p: 3, textAlign: 'center' }}>
              <Typography variant="body2">{cvError ? t(cvError) : (cvUrl && !isPdf ? t("Tệp DOCX cần được tải xuống để xem.") : t("Không thể tải CV. Vui lòng thử lại."))}</Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </>
  );
}
