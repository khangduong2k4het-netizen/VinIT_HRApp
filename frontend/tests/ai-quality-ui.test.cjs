const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function load(relativePath) {
  const filename = path.join(__dirname, '..', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }, fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}
const { chartPoints, fillMissingPeriods, localIsoDate, markerIndex, markerKindKey, pct, periodLabel, trendStatement } = load('src/lib/aiQuality.ts');

const point = (rate, low, high, insufficient = false) => ({ rate, ci_low: low, ci_high: high, count: 5, total: 20, insufficient });
const row = (period, p) => ({ period, qa_random_sample: p });

test('rates are shown only when present, as one-decimal percentages', () => {
  assert.equal(pct(null), '—');
  assert.equal(pct(0.12345), '12.3%');
});

test('insufficient periods keep their counts but carry no rate', () => {
  const [a] = chartPoints([row('2026-01-05', point(null, null, null, true))], r => r.qa_random_sample);
  assert.deepEqual([a.value, a.insufficient, a.count, a.total], [null, true, 5, 20]);
});

test('a trend is claimed only when the confidence intervals do not overlap', () => {
  const pick = r => r.qa_random_sample;
  const series = rows => chartPoints(rows, pick);
  assert.equal(trendStatement(series([row('a', point(0.30, 0.2, 0.4)), row('b', point(0.10, 0.05, 0.15))])), 'BETTER');
  assert.equal(trendStatement(series([row('a', point(0.10, 0.05, 0.15)), row('b', point(0.30, 0.2, 0.4))])), 'WORSE');
  assert.equal(trendStatement(series([row('a', point(0.20, 0.1, 0.3)), row('b', point(0.25, 0.15, 0.35))])), 'NO_CLEAR_CHANGE');
  assert.equal(trendStatement(series([row('a', point(0.2, 0.1, 0.3)), row('b', point(null, null, null, true))])), 'NOT_ENOUGH_DATA');
});

test('markers attach to the period that contains their date', () => {
  const periods = ['2026-01-05', '2026-01-12', '2026-01-19'];
  assert.equal(markerIndex(periods, '2026-01-14'), 1);
  assert.equal(markerIndex(periods, '2026-01-05'), 0);
  assert.equal(markerIndex(periods, '2025-12-31'), -1);
});

test('period labels follow the grain', () => {
  assert.equal(periodLabel('2026-03-09', 'week'), '09/03');
  assert.equal(periodLabel('2026-03-01', 'month'), '03/2026');
});

test('fillMissingPeriods inserts zero-count placeholders for empty weeks and months', () => {
  const weekly = fillMissingPeriods([
    { period: '2026-01-05', value: 0.2, low: 0.1, high: 0.3, count: 4, total: 20, insufficient: false },
    { period: '2026-01-19', value: 0.1, low: 0.05, high: 0.2, count: 2, total: 20, insufficient: false },
  ], 'week');
  assert.deepEqual(weekly.map(p => p.period), ['2026-01-05', '2026-01-12', '2026-01-19']);
  assert.equal(weekly[1].insufficient, true);
  assert.equal(weekly[1].total, 0);

  const monthly = fillMissingPeriods([
    { period: '2026-01-01', value: 0.2, low: 0.1, high: 0.3, count: 4, total: 20, insufficient: false },
    { period: '2026-03-01', value: 0.1, low: 0.05, high: 0.2, count: 2, total: 20, insufficient: false },
  ], 'month');
  assert.deepEqual(monthly.map(p => p.period), ['2026-01-01', '2026-02-01', '2026-03-01']);
  assert.equal(markerIndex(monthly.map(p => p.period), '2026-02-15'), 1);
});

test('markerKindKey uses source for automatic VERSION markers and kind for manual ones', () => {
  assert.equal(markerKindKey({ kind: 'VERSION', source: 'MATCHING_POLICY' }), 'MATCHING_POLICY');
  assert.equal(markerKindKey({ kind: 'VERSION', source: 'RULES' }), 'RULES');
  assert.equal(markerKindKey({ kind: 'MANUAL', source: 'ADMIN' }), 'MANUAL');
});

test('localIsoDate formats using local calendar date', () => {
  assert.equal(localIsoDate(new Date(2026, 10, 5, 0, 15, 0)), '2026-11-05');
});
