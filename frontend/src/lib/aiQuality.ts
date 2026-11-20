// P3-2 AI quality dashboard: types and pure helpers (kept free of React so they can be unit tested).

export type Proportion = { count: number; total: number; rate: number | null; ci_low: number | null; ci_high: number | null; insufficient: boolean };
export type TrendRow = {
  period: string;
  overrides: Proportion & { advanced_despite_ai: number; rejected_despite_ai: number };
  qa_random_sample: Proportion;
  qa_risk_group: Proportion;
  qa_completed: number;
  qa_flags_by_category: Record<string, number>;
  assessments: { completed: number; average_evidence_coverage: number | null; needs_verification: Proportion; unclear_criteria: Proportion };
};
export type Trends = {
  range: { date_from: string; date_to: string; grain: 'week' | 'month' };
  min_sample: number;
  series: TrendRow[];
  qa_backlog: { open_cases: number; oldest_created_at: string | null };
};
export type Marker = { date: string; kind: string; source?: string; title: string; note: string | null; marker_id?: string };
export type BreakdownRow = {
  key: string | null; label?: string | null; count?: number; share?: number | null; completed?: number;
  overrides?: Proportion; qa_random_sample?: Proportion; needs_verification?: Proportion; average_evidence_coverage?: number | null;
};

export function pct(value: number | null | undefined): string {
  return value == null ? '—' : `${Math.round(value * 1000) / 10}%`;
}

/** "12/3 (25%)" for a reliable rate, "3/19 · chưa đủ dữ liệu" is composed by the caller. */
export function counts(p: Proportion): string {
  return `${p.count}/${p.total}`;
}

/** Format a Date as YYYY-MM-DD in the browser's local timezone (avoids UTC day-shift before 07:00 VN). */
export function localIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Pick the display key for a change marker chip (backend sends kind='VERSION' + source='RULES'|'PROMPT'|'MATCHING_POLICY'). */
export function markerKindKey(m: Pick<Marker, 'kind' | 'source'>): string {
  return m.kind === 'VERSION' && m.source ? m.source : m.kind;
}

export type ChartPoint = { period: string; value: number | null; low: number | null; high: number | null; count: number; total: number; insufficient: boolean };

export function chartPoints(series: TrendRow[], pick: (row: TrendRow) => Proportion): ChartPoint[] {
  return series.map(row => {
    const p = pick(row);
    return { period: row.period, value: p.rate, low: p.ci_low, high: p.ci_high, count: p.count, total: p.total, insufficient: p.insufficient };
  });
}

function nextPeriod(period: string, grain: 'week' | 'month'): string {
  const [y, m, d] = period.split('-').map(Number);
  if (grain === 'month') {
    const dt = new Date(Date.UTC(y, m, 1));
    return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-01`;
  }
  const dt = new Date(Date.UTC(y, m - 1, d + 7));
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
}

/** Insert zero-count placeholders for empty weeks/months so the chart X-axis stays evenly spaced
 * and change markers land on the right period. Capped at 120 periods to guard against malformed inputs. */
export function fillMissingPeriods(points: ChartPoint[], grain: 'week' | 'month'): ChartPoint[] {
  if (points.length <= 1) return points;
  const byPeriod = new Map(points.map(p => [p.period, p]));
  const first = points[0].period;
  const last = points[points.length - 1].period;
  const filled: ChartPoint[] = [];
  let cursor = first;
  for (let steps = 0; cursor <= last && steps < 120; steps += 1) {
    filled.push(byPeriod.get(cursor) || {
      period: cursor, value: null, low: null, high: null, count: 0, total: 0, insufficient: true,
    });
    const next = nextPeriod(cursor, grain);
    if (next <= cursor) break;
    cursor = next;
  }
  return filled.length >= points.length ? filled : points;
}

/** Whether the latest and earliest reliable points differ beyond their intervals. Never claims a trend otherwise. */
export function trendStatement(points: ChartPoint[]): 'BETTER' | 'WORSE' | 'NO_CLEAR_CHANGE' | 'NOT_ENOUGH_DATA' {
  const reliable = points.filter(p => !p.insufficient && p.value != null && p.low != null && p.high != null);
  if (reliable.length < 2) return 'NOT_ENOUGH_DATA';
  const first = reliable[0];
  const last = reliable[reliable.length - 1];
  if ((last.low as number) > (first.high as number)) return 'WORSE';   // a higher rate is worse for error rates (or higher disagreement for overrides)
  if ((last.high as number) < (first.low as number)) return 'BETTER';
  return 'NO_CLEAR_CHANGE';
}

/** Markers placed on a period axis: the marker belongs to the last period that starts on or before it. */
export function markerIndex(periods: string[], date: string): number {
  let index = -1;
  periods.forEach((period, i) => { if (period <= date) index = i; });
  return index;
}

export function periodLabel(period: string, grain: 'week' | 'month'): string {
  const [year, month, day] = period.split('-');
  return grain === 'month' ? `${month}/${year}` : `${day}/${month}`;
}
