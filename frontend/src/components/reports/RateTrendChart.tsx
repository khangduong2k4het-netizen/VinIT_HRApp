'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { useI18n } from '@/i18n/I18nProvider';
import { markerIndex, pct, periodLabel, type ChartPoint, type Marker } from '@/lib/aiQuality';

// One series per chart, one brand hue, no legend. The shaded band is the 95% interval.
// A period with too few cases is drawn as a hollow grey tick with no rate, never as a number.
const LINE = '#0A2B57';
const BAND = 'rgba(10,43,87,0.14)';
const MUTED = '#94A3B8';
const MARK = '#C8102E';

export default function RateTrendChart({ points, markers, grain, ariaLabel }: {
  points: ChartPoint[]; markers: Marker[]; grain: 'week' | 'month'; ariaLabel: string;
}) {
  const { t } = useI18n();
  const width = 720, height = 220, left = 44, right = 12, top = 12, bottom = 34;
  const innerW = width - left - right, innerH = height - top - bottom;
  const n = points.length;
  const x = (i: number) => left + (n <= 1 ? innerW / 2 : (innerW * i) / (n - 1));
  const y = (v: number) => top + innerH * (1 - v);
  const reliable = points.map((p, i) => ({ p, i })).filter(({ p }) => !p.insufficient && p.value != null);
  const line = reliable.map(({ p, i }, k) => `${k ? 'L' : 'M'}${x(i)},${y(p.value as number)}`).join(' ');
  const band = reliable.length > 1
    ? `M${reliable.map(({ p, i }) => `${x(i)},${y(p.high as number)}`).join(' L')} L${[...reliable].reverse().map(({ p, i }) => `${x(i)},${y(p.low as number)}`).join(' L')} Z`
    : '';
  const periods = points.map(p => p.period);
  const labelEvery = Math.max(1, Math.ceil(n / 8));
  return (
    <Box>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {[0, 0.25, 0.5, 0.75, 1].map(g => (
          <g key={g}>
            <line x1={left} x2={width - right} y1={y(g)} y2={y(g)} stroke="#E2E8F0" />
            <text x={left - 6} y={y(g) + 4} textAnchor="end" fontSize="11" fill="#475569">{`${g * 100}%`}</text>
          </g>
        ))}
        {markers.map((m, k) => {
          const i = markerIndex(periods, m.date);
          if (i < 0) return null;
          return (
            <g key={`${m.date}-${k}`}>
              <title>{`${m.date}: ${m.title}`}</title>
              <line x1={x(i)} x2={x(i)} y1={top} y2={top + innerH} stroke={MARK} strokeDasharray="3 3" />
            </g>
          );
        })}
        {band && <path d={band} fill={BAND} />}
        {line && <path d={line} fill="none" stroke={LINE} strokeWidth="2" />}
        {points.map((p, i) => (
          <g key={p.period}>
            <title>{p.insufficient
              ? `${periodLabel(p.period, grain)}: ${p.count}/${p.total} · ${t('chưa đủ dữ liệu')}`
              : `${periodLabel(p.period, grain)}: ${pct(p.value)} (${p.count}/${p.total}), 95%: ${pct(p.low)}–${pct(p.high)}`}</title>
            {p.insufficient
              ? <circle cx={x(i)} cy={y(0)} r="4" fill="#fff" stroke={MUTED} strokeWidth="1.5" />
              : <circle cx={x(i)} cy={y(p.value as number)} r="4" fill={LINE} />}
            {i % labelEvery === 0 && (
              <text x={x(i)} y={height - 12} textAnchor="middle" fontSize="11" fill="#475569">{periodLabel(p.period, grain)}</text>
            )}
          </g>
        ))}
      </svg>
      <Typography variant="caption" color="text.secondary">
        {t('Vòng rỗng ở đáy: kỳ chưa đủ dữ liệu để tính tỷ lệ. Dải mờ: khoảng tin cậy 95%. Vạch đỏ: mốc thay đổi.')}
      </Typography>
    </Box>
  );
}
