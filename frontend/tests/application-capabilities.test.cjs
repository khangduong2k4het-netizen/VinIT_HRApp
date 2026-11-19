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

const { readApplicationCapabilities } = loadTypeScriptModule('src/lib/applicationCapabilities.ts');

const CAPABILITIES = {
  view_cv: true,
  view_evidence: true,
  update_status: true,
  review_evidence: false,
  manage_hr_notes: false,
  edit_profile: true,
  view_status_history: true,
  reprocess_cv: true,
};

const application = (overrides = {}) => ({ application_id: 'app-1', ...overrides });

test('the server object is read verbatim, one flag per action', () => {
  const caps = readApplicationCapabilities(application({ capabilities: CAPABILITIES }));
  assert.deepEqual(caps, {
    viewCv: true,
    viewEvidence: true,
    updateStatus: true,
    reviewEvidence: false,
    manageHrNotes: false,
    editProfile: true,
    viewStatusHistory: true,
    reprocessCv: true,
  });
});

test('a status-only reviewer is not offered evidence review', () => {
  // Global ADMIN: may change status, may not record a criterion review. The
  // review endpoint answers 403, so the screen must not show those buttons.
  const caps = readApplicationCapabilities(application({
    can_update_status: true,
    can_manage_hr_notes: false,
    capabilities: CAPABILITIES,
  }));
  assert.equal(caps.updateStatus, true);
  assert.equal(caps.reviewEvidence, false, 'update_status must never imply review_evidence');
});

test('payloads that predate the object fall back to the flat flags', () => {
  const caps = readApplicationCapabilities(application({
    can_view_cv: true,
    can_view_assessment_evidence: true,
    can_update_status: true,
    can_manage_hr_notes: true,
  }));
  assert.equal(caps.viewCv, true);
  assert.equal(caps.viewEvidence, true);
  assert.equal(caps.reviewEvidence, true);
  assert.equal(caps.manageHrNotes, true);
  assert.equal(caps.viewStatusHistory, true, 'status history shares the update gate');
  assert.equal(caps.reprocessCv, true, 'reprocess shares the update gate');
});

test('a missing capability is false, never undefined', () => {
  // A backend deployed before a new flag must hide the control rather than let
  // the reviewer press it and collect a 403.
  const caps = readApplicationCapabilities(application({ can_view_cv: true, capabilities: {} }));
  assert.equal(caps.viewCv, true);
  for (const key of ['viewEvidence', 'updateStatus', 'reviewEvidence', 'manageHrNotes', 'editProfile', 'viewStatusHistory', 'reprocessCv']) {
    assert.equal(caps[key], false, `${key} must default to false`);
  }
});
