'use client';

import * as React from 'react';
import { useState } from 'react';
import { Box, Paper, Stack, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { fillMissingPeriods, markerIndex, pct, periodLabel, type ChartPoint, type Marker } from '@/lib/aiQuality';

// One series per chart, VinUni Navy hue, 95% Wilson CI band, interactive hover crosshair.
// A period with too few cases is drawn as a hollow slate dot with no rate, never as a number.
const LINE = '#0A2B57';
const BAND = 'rgba(10, 43, 87, 0.11)';
const MUTED = '#94A3B8';
const MARK = '#C72127';

export default function RateTrendChart({ points, markers, grain, ariaLabel }: {
  points: ChartPoint[]; markers: Marker[]; grain: 'week' | 'month'; ariaLabel: string;
}) {
  const { t } = useI18n();
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const series = fillMissingPeriods(points, grain);
  const width = 720, height = 228, left = 44, right = 16, top = 16, bottom = 36;
  const innerW = width - left - right, innerH = height - top - bottom;
  const n = series.length;
  const x = (i: number) => left + (n <= 1 ? innerW / 2 : (innerW * i) / (n - 1));
  const y = (v: number) => top + innerH * (1 - v);
  const reliable = series.map((p, i) => ({ p, i })).filter(({ p }) => !p.insufficient && p.value != null);
  const line = reliable.map(({ p, i }, k) => `${k ? 'L' : 'M'}${x(i)},${y(p.value as number)}`).join(' ');
  const band = reliable.length > 1
    ? `M${reliable.map(({ p, i }) => `${x(i)},${y(p.high as number)}`).join(' L')} L${[...reliable].reverse().map(({ p, i }) => `${x(i)},${y(p.low as number)}`).join(' L')} Z`
    : '';
  const periods = series.map(p => p.period);
  const labelEvery = Math.max(1, Math.ceil(n / 8));
  const hovered = hoveredIdx != null ? series[hoveredIdx] : null;
  const hoveredMarkers = hoveredIdx != null ? markers.filter(m => markerIndex(periods, m.date) === hoveredIdx) : [];

  return (
    <Box sx={{ position: 'relative' }} onMouseLeave={() => setHoveredIdx(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {[0, 0.25, 0.5, 0.75, 1].map(g => (
          <g key={g}>
            <line x1={left} x2={width - right} y1={y(g)} y2={y(g)} stroke="#E5EAF0" strokeDasharray={g === 0 ? undefined : '2 3'} />
            <text x={left - 8} y={y(g) + 4} textAnchor="end" fontSize="11" fill="#64748B">{`${g * 100}%`}</text>
          </g>
        ))}

        {hoveredIdx != null && (
          <line x1={x(hoveredIdx)} x2={x(hoveredIdx)} y1={top} y2={top + innerH} stroke="#CBD5E1" strokeWidth="1" />
        )}

        {markers.map((m, k) => {
          const i = markerIndex(periods, m.date);
          if (i < 0) return null;
          return (
            <g key={`${m.date}-${k}`}>
              <title>{`${m.date}: ${m.title}`}</title>
              <line x1={x(i)} x2={x(i)} y1={top} y2={top + innerH} stroke={MARK} strokeWidth="1.5" strokeDasharray="3 3" />
              <circle cx={x(i)} cy={top + 2} r="3" fill={MARK} />
            </g>
          );
        })}

        {band && <path d={band} fill={BAND} />}
        {line && <path d={line} fill="none" stroke={LINE} strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" />}

        {series.map((p, i) => {
          const isHovered = hoveredIdx === i;
          const cy = p.insufficient ? y(0) : y(p.value as number);
          return (
            <g key={p.period} onMouseEnter={() => setHoveredIdx(i)} style={{ cursor: 'pointer' }}>
              <title>{p.insufficient
                ? `${periodLabel(p.period, grain)}: ${p.count}/${p.total} · ${t('chưa đủ dữ liệu')}`
                : `${periodLabel(p.period, grain)}: ${pct(p.value)} (${p.count}/${p.total}), 95%: ${pct(p.low)}–${pct(p.high)}`}</title>
              {/* Wider invisible hit area for effortless hovering */}
              <rect
                x={x(i) - Math.max(10, innerW / Math.max(n * 2, 2))}
                y={top}
                width={Math.max(20, innerW / Math.max(n, 1))}
                height={innerH}
                fill="transparent"
              />
              {p.insufficient ? (
                <circle cx={x(i)} cy={cy} r={isHovered ? 5.5 : 3.75} fill="#FFFFFF" stroke={isHovered ? LINE : MUTED} strokeWidth="1.75" />
              ) : (
                <circle cx={x(i)} cy={cy} r={isHovered ? 6 : 4} fill={LINE} stroke="#FFFFFF" strokeWidth="1.75" />
              )}
              {i % labelEvery === 0 && (
                <text x={x(i)} y={height - 12} textAnchor="middle" fontSize="11" fill={isHovered ? '#0F172A' : '#64748B'} fontWeight={isHovered ? 600 : 400}>
                  {periodLabel(p.period, grain)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Interactive hover readout bar */}
      {hovered ? (
        <Paper
          elevation={0}
          sx={{
            mt: 1,
            px: 1.5,
            py: 0.75,
            borderRadius: '8px',
            bgcolor: '#F8FAFC',
            border: '1px solid #E5EAF0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 1.5,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="caption" className="tabular-nums" sx={{ color: '#0F172A', fontWeight: 600 }}>
            {periodLabel(hovered.period, grain)}:{' '}
            {hovered.insufficient
              ? `${hovered.count}/${hovered.total} · ${t('chưa đủ dữ liệu')}`
              : `${pct(hovered.value)} (${hovered.count}/${hovered.total}) · 95% CI [${pct(hovered.low)}–${pct(hovered.high)}]`}
          </Typography>
          {hoveredMarkers.length > 0 && (
            <Typography variant="caption" sx={{ color: '#C72127', fontWeight: 600 }}>
              {hoveredMarkers.map(m => m.title).join(' · ')}
            </Typography>
          )}
        </Paper>
      ) : (
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            {t('Vòng rỗng ở đáy: kỳ chưa đủ dữ liệu để tính tỷ lệ. Dải mờ: khoảng tin cậy 95%. Vạch đỏ: mốc thay đổi.')}
          </Typography>
        </Stack>
      )}
    </Box>
  );
}
