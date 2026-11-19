const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(__dirname, '..', relativePath);
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'require', output)(loaded, loaded.exports, require);
  return loaded.exports;
}

const retention = loadTypeScriptModule('src/lib/retention.ts');
const {
  summarizeRetentionCases, canConfirmRetentionCase, canCancelRetentionCase,
  hasApplicationTimeline, retentionStatusLabel, retentionExecutionLabel, daysUntilRetentionDue,
} = retention;

const CASE = {
  retention_case_id: 'case-1',
  application_id: 'app-1',
  application_opaque_id: 'opaque-1',
  position_id: 'p1',
  policy_version: 'rp-1',
  position_closed_at: '2025-01-01T00:00:00Z',
  due_date: '2026-01-01T00:00:00Z',
  status: 'PENDING',
  execution_status: null,
  execution_in_progress_or_recovery: false,
  is_due: true,
  confirmed_by: null,
  confirmed_at: null,
  created_at: '2026-01-02T00:00:00Z',
};
const make = overrides => ({ ...CASE, ...overrides });

test('the summary counts each case by the state HR acts on', () => {
  const summary = summarizeRetentionCases([
    make(),
    make({ retention_case_id: 'c2', status: 'PENDING', is_due: false }),
    make({ retention_case_id: 'c3', status: 'SCHEDULED_FOR_DELETION' }),
    make({ retention_case_id: 'c4', status: 'CANCELLED', is_due: false }),
    make({ retention_case_id: 'c5', status: 'DELETED', is_due: false }),
    make({ retention_case_id: 'c6', status: 'SCHEDULED_FOR_DELETION', execution_status: 'PROCESSING', execution_in_progress_or_recovery: true }),
  ]);
  // c3 and c6 are scheduled/processing and still marked due; only the ones the
  // server calls due are counted, this test does not recompute dates.
  assert.deepEqual(summary, { total: 6, due: 3, pending: 2, scheduled: 2, cancelled: 1, deleted: 1, processing: 1 });
});

test('confirm is offered only for a due case with no execution in flight', () => {
  assert.equal(canConfirmRetentionCase(make()), true);
  assert.equal(canConfirmRetentionCase(make({ is_due: false })), false, 'the backend rejects a case before its due date');
  assert.equal(canConfirmRetentionCase(make({ status: 'SCHEDULED_FOR_DELETION' })), false, 'already confirmed');
  assert.equal(canConfirmRetentionCase(make({ status: 'CANCELLED' })), false);
  assert.equal(canConfirmRetentionCase(make({ execution_status: 'PROCESSING' })), false);
  assert.equal(canConfirmRetentionCase(make({ execution_in_progress_or_recovery: true })), false);
});

test('cancel is offered before execution, never while a deletion is running', () => {
  assert.equal(canCancelRetentionCase(make()), true);
  assert.equal(canCancelRetentionCase(make({ status: 'SCHEDULED_FOR_DELETION' })), true);
  assert.equal(canCancelRetentionCase(make({ status: 'DELETED' })), false);
  assert.equal(canCancelRetentionCase(make({ status: 'SCHEDULED_FOR_DELETION', execution_status: 'PROCESSING' })), false);
  assert.equal(canCancelRetentionCase(make({ execution_in_progress_or_recovery: true })), false);
});

test('a deleted application has no decision timeline left', () => {
  assert.equal(hasApplicationTimeline(make()), true);
  assert.equal(hasApplicationTimeline(make({ application_id: null })), false);
  assert.equal(hasApplicationTimeline(make({ status: 'DELETED' })), false);
});

test('unknown states fall back to the raw code instead of rendering undefined', () => {
  assert.equal(retentionStatusLabel('SOMETHING_NEW'), 'SOMETHING_NEW');
  assert.equal(retentionStatusLabel('PENDING'), 'Chờ xác nhận');
  assert.equal(retentionExecutionLabel(null), 'Chưa chạy');
  assert.equal(retentionExecutionLabel('PROCESSING'), 'Đang thực thi');
  assert.equal(retentionExecutionLabel('SOMETHING_NEW'), 'SOMETHING_NEW');
});

test('the due countdown is honest about missing or bad dates', () => {
  const now = new Date('2026-11-19T00:00:00Z');
  assert.equal(daysUntilRetentionDue('2026-11-22T00:00:00Z', now), 3);
  assert.equal(daysUntilRetentionDue('2026-11-16T00:00:00Z', now), -3);
  assert.equal(daysUntilRetentionDue(null, now), null);
  assert.equal(daysUntilRetentionDue('not-a-date', now), null);
});
