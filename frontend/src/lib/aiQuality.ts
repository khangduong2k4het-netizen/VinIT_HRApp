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

export type ChartPoint = { period: string; value: number | null; low: number | null; high: number | null; count: number; total: number; insufficient: boolean };

export function chartPoints(series: TrendRow[], pick: (row: TrendRow) => Proportion): ChartPoint[] {
  return series.map(row => {
    const p = pick(row);
    return { period: row.period, value: p.rate, low: p.ci_low, high: p.ci_high, count: p.count, total: p.total, insufficient: p.insufficient };
  });
}

/** Whether the latest and earliest reliable points differ beyond their intervals. Never claims a trend otherwise. */
export function trendStatement(points: ChartPoint[]): 'BETTER' | 'WORSE' | 'NO_CLEAR_CHANGE' | 'NOT_ENOUGH_DATA' {
  const reliable = points.filter(p => !p.insufficient && p.value != null && p.low != null && p.high != null);
  if (reliable.length < 2) return 'NOT_ENOUGH_DATA';
  const first = reliable[0];
  const last = reliable[reliable.length - 1];
  if ((last.low as number) > (first.high as number)) return 'WORSE';   // a higher rate is worse for override and error rates
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
