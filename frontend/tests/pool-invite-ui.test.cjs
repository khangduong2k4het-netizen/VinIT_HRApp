// Talent Pool invitations (ND13): written only from a scan, with a confirmation, never from the pool list.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = rel => fs.readFileSync(path.join(__dirname, '..', 'src', rel), 'utf8');

test('POOL_INVITE is not a general compose choice and needs a scan', () => {
  const dialog = read('components/candidates/CandidateEmailDialog.tsx');
  const list = dialog.slice(dialog.indexOf('export const COMPOSE_TEMPLATES'), dialog.indexOf('export const TEMPLATE_LABELS'));
  assert.doesNotMatch(list, /POOL_INVITE/);
  assert.match(dialog, /poolScanId/);
  assert.match(dialog, /scan_id: poolScanId/);
  assert.match(dialog, /!draft && !poolScanId/);
});

test('sending a pool invitation asks for confirmation naming the recipient and the purpose', () => {
  const dialog = read('components/candidates/CandidateEmailDialog.tsx');
  assert.match(dialog, /confirmPool/);
  assert.match(dialog, /Xác nhận gửi thư mời/);
  assert.match(dialog, /Bạn sắp gửi thư mời trao đổi tới/);
  assert.match(dialog, /isRejection \|\| isPoolInvite/);
});

test('the invitation opens only from the scan contact dialog, not from the pool list', () => {
  const scan = read('components/talent-pool/ScanPanel.tsx');
  assert.match(scan, /poolScanId=\{scan\.scan_id\}/);
  const page = read('app/talent-pool/page.tsx');
  assert.doesNotMatch(page, /CandidateEmailDialog/);
  assert.doesNotMatch(page, /Mời trao đổi/);
});

test('the client passes the scan to compose and create', () => {
  const api = read('lib/api.ts');
  assert.match(api, /compose: \(applicationId: string, templateCode: EmailTemplateCode, scanId\?: string\)/);
  assert.match(api, /scan_id\?: string/);
});
