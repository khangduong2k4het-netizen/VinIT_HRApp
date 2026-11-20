const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function helpers(fetch) {
  const filename = path.join(__dirname, '../src/lib/publicApply.ts');
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const loaded = { exports: {} };
  new Function('module', 'exports', 'fetch', output)(loaded, loaded.exports, fetch);
  return loaded.exports;
}

test('no submission or implied consent when processing permission is absent', async () => {
  const api = helpers(() => assert.fail('must not make a request'));
  assert.deepEqual(await api.submitApplication('REQ-1', new File(['CV'], 'cv.pdf'), false, ''),
    { ok: false, failure: 'CONSENT' });
});

test('the single consent sends notice v4 without an HR token', async () => {
  const api = helpers(async (url, options) => {
    assert.equal(url, '/v1/public/positions/REQ%2F1/apply');
    assert.equal(options.body.get('consent_processing'), 'true');
    assert.equal(options.body.get('consent_talent_pool'), null);
    assert.equal(options.body.get('notice_version'), 'v4');
    assert.equal(options.headers, undefined);
    return Response.json({ status: 'received', withdrawal_token: 'a'.repeat(64) }, { status: 202 });
  });
  const result = await api.submitApplication('REQ/1', new File(['CV'], 'cv.pdf'), true, '');
  assert.equal(result.ok, true);
  assert.equal(result.withdrawalToken, 'a'.repeat(64));
});

test('a missing receipt or missing withdrawal token is not reported as success', async () => {
  for (const receipt of [{}, { status: 'received' }, { status: 'received', withdrawal_token: 'invalid' }]) {
    const api = helpers(async () => Response.json(receipt, { status: 202 }));
    assert.deepEqual(await api.submitApplication('REQ-1', new File(['CV'], 'cv.pdf'), true, ''),
      { ok: false, failure: 'NETWORK' });
  }
});

test('stale consent, throttling and scanner outages get actionable failure types', async () => {
  for (const [status, failure] of [[409, 'NOTICE_CHANGED'], [429, 'RATE_LIMIT'], [503, 'UNAVAILABLE'], [413, 'FILE'], [404, 'POSITION_CLOSED']]) {
    const api = helpers(async () => Response.json({}, { status }));
    assert.deepEqual(await api.submitApplication('REQ-1', new File(['CV'], 'cv.pdf'), true, ''), { ok: false, failure });
  }
});
