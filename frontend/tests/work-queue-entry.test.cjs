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

const { workQueueListHref, workQueueNextHref } = loadTypeScriptModule('src/lib/workQueueEntry.ts');

const verificationItem = {
  target: { pathname: '/positions/p1/applicants', search: 'queue=NEEDS_VERIFICATION' },
  next_application_id: 'app-7',
};

test('việc gắn với hồ sơ mở thẳng hồ sơ đó và giữ nguyên bộ lọc trong URL', () => {
  assert.equal(
    workQueueNextHref(verificationItem),
    '/positions/p1/applicants/app-7?queue=NEEDS_VERIFICATION',
    'trang hồ sơ dựng lại hàng đợi từ queue trong URL để hiện đúng tiến độ 3/17',
  );
});

test('danh sách đã lọc vẫn là đích thứ hai, không đổi so với trước', () => {
  assert.equal(workQueueListHref(verificationItem), '/positions/p1/applicants?queue=NEEDS_VERIFICATION');
  assert.equal(workQueueNextHref(verificationItem)?.startsWith(workQueueListHref(verificationItem).split('?')[0]), true);
});

test('việc không gắn với hồ sơ nào thì không có link trực tiếp', () => {
  const setup = { target: { pathname: '/positions/p1', search: 'tab=criteria' } };
  assert.equal(workQueueNextHref(setup), null);
  assert.equal(workQueueNextHref({ ...setup, next_application_id: '' }), null);
  assert.equal(workQueueNextHref({ ...setup, next_application_id: '   ' }), null);
  assert.equal(workQueueNextHref({ ...setup, next_application_id: null }), null);
});

test('id hồ sơ được encode và đường dẫn thừa "/" không tạo "//"', () => {
  assert.equal(
    workQueueNextHref({ target: { pathname: '/positions/p1/applicants/' }, next_application_id: 'a b' }),
    '/positions/p1/applicants/a%20b',
  );
});
