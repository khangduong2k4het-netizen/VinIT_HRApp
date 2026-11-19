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
const { chartPoints, trendStatement, markerIndex, pct, periodLabel } = load('src/lib/aiQuality.ts');

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
