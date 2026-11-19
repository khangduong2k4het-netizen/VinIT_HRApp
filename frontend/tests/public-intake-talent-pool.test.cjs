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

const { buildWithdrawalReceiptText, failureFromStatus, filterPublicPositions, MAX_FILE_BYTES, validateCv } = load('src/lib/publicApply.ts');
const { buildMailtoHref, filterPoolMarks, poolRef, scanIsActive, scoreText, SKIP_REASONS } = load('src/lib/talentPool.ts');

test('validateCv checks presence, extension and max file size', () => {
  assert.equal(validateCv(null), 'MISSING');
  assert.equal(validateCv({ name: 'resume.exe', size: 100 }), 'TYPE');
  assert.equal(validateCv({ name: 'CV.PDF', size: MAX_FILE_BYTES + 1 }), 'SIZE');
  assert.equal(validateCv({ name: 'candidate.docx', size: 50_000 }), null);
  assert.equal(validateCv({ name: 'scan.PNG', size: 50_000 }), null);
});

test('failureFromStatus maps HTTP statuses to stable public error codes', () => {
  assert.equal(failureFromStatus(429), 'RATE_LIMIT');
  assert.equal(failureFromStatus(503), 'UNAVAILABLE');
  assert.equal(failureFromStatus(404), 'POSITION_CLOSED');
  assert.equal(failureFromStatus(413), 'FILE');
  assert.equal(failureFromStatus(400), 'FILE');
  assert.equal(failureFromStatus(500), 'NETWORK');
});

test('talentPool helpers format opaque refs, scores and active scan states', () => {
  assert.equal(poolRef('a1b2c3d4-e5f6-7890-1234-567890abcdef'), '#A1B2C3D4');
  assert.equal(scoreText(null), '—');
  assert.equal(scoreText(87.64), '87.6%');
  assert.equal(scanIsActive('PENDING'), true);
  assert.equal(scanIsActive('PROCESSING'), true);
  assert.equal(scanIsActive('COMPLETED'), false);
  assert.equal(scanIsActive('FAILED'), false);
  assert.ok(SKIP_REASONS.DUPLICATE_PHONE);
});

test('buildWithdrawalReceiptText includes position, token and withdraw URL', () => {
  const txt = buildWithdrawalReceiptText('IT-01', 'Data Engineer', 'a'.repeat(64), 'https://hra.vinuni.edu.vn/');
  assert.ok(txt.includes('IT-01') && txt.includes('Data Engineer'));
  assert.ok(txt.includes('a'.repeat(64)));
  assert.ok(txt.includes('https://hra.vinuni.edu.vn/apply/withdraw'));
});

test('buildMailtoHref encodes recipient, subject and body safely', () => {
  const href = buildMailtoHref(' candidate@example.com ', 'Hello & Welcome', 'Line 1\nLine 2');
  assert.ok(href.startsWith('mailto:candidate%40example.com?subject='));
  assert.ok(href.includes('Hello%20%26%20Welcome') && href.includes('Line%201%0ALine%202'));
});

test('filterPoolMarks filters by query, reason and eligibility', () => {
  const rows = [
    { application_id: 'aaaa1111-0000-0000-0000-000000000000', reason_code: 'STRONG_FIT', position_title: 'Backend Engineer', position_code: 'ENG-01', eligible: true },
    { application_id: 'bbbb2222-0000-0000-0000-000000000000', reason_code: 'NEAR_MISS', position_title: 'Accountant', position_code: 'FIN-02', eligible: false },
  ];
  assert.equal(filterPoolMarks(rows, { query: 'fin-02' }).length, 1);
  assert.equal(filterPoolMarks(rows, { query: '#AAAA1111' }).length, 1);
  assert.equal(filterPoolMarks(rows, { reason: 'STRONG_FIT' }).length, 1);
  assert.equal(filterPoolMarks(rows, { eligibility: 'ELIGIBLE' }).length, 1);
  assert.equal(filterPoolMarks(rows, { eligibility: 'INELIGIBLE' }).length, 1);
});

test('filterPublicPositions filters by search text and unit', () => {
  const jobs = [
    { code: 'IT-01', title: 'Data Engineer', unit: 'IT Office', location: 'Hanoi', employment_type: 'FULL_TIME' },
    { code: 'FIN-02', title: 'Senior Accountant', unit: 'Finance', location: 'Hanoi', employment_type: 'FULL_TIME' },
  ];
  assert.equal(filterPublicPositions(jobs, { query: 'data' }).length, 1);
  assert.equal(filterPublicPositions(jobs, { query: 'fin-02' }).length, 1);
  assert.equal(filterPublicPositions(jobs, { unit: 'Finance' }).length, 1);
  assert.equal(filterPublicPositions(jobs, { unit: 'IT Office', query: 'accountant' }).length, 0);
});

test('the Talent Pool panel reloads its state when the application status changes', () => {
  const read = (file) => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
  const page = read('src/app/positions/[id]/applicants/[applicantId]/page.tsx');
  const panel = read('src/components/talent-pool/TalentPoolPanel.tsx');
  assert.match(page, /<TalentPoolPanel[^>]*refreshKey=\{application\.application_status\}/);
  assert.match(panel, /refreshKey\?: string \| null/);
  assert.match(panel, /\[applicationId, refreshKey\]/);
});

test('narrow /apply clamps the job description and offers a jump to the form', () => {
  const read = (file) => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
  const page = read('src/app/apply/page.tsx');
  const clamp = read('src/components/public/CollapsibleText.tsx');
  const en = require('../src/i18n/en.json');
  // Both long texts go through the clamp, switched on below the two-column breakpoint only.
  assert.match(page, /breakpoints\.down\('lg'\)/);
  assert.equal((page.match(/<CollapsibleText enabled=\{narrow\}>/g) || []).length, 2);
  // A button scrolls to the form, which carries the id it targets.
  assert.match(page, /getElementById\('apply-form'\)/);
  assert.match(page, /id="apply-form"/);
  assert.match(page, /\{narrow && \(\s*<Button/);
  // The clamp has a fade, an expanded state for assistive tech, and a 40px touch target.
  assert.match(clamp, /linear-gradient/);
  assert.match(clamp, /aria-expanded=\{expanded\}/);
  assert.match(clamp, /minHeight: 40/);
  assert.match(clamp, /collapsedHeight = 360/);
  for (const key of ['Xem thêm', 'Thu gọn', 'Nộp hồ sơ ngay']) assert.ok(en[key], `missing English text for ${key}`);
});

test('a collapsed sidebar has a clear, labelled, 40px way back near the top', () => {
  const sidebar = fs.readFileSync(path.join(__dirname, '..', 'src/components/layout/Sidebar.tsx'), 'utf8');
  // One button under the header and one in the footer, both labelled and with a tooltip.
  assert.equal((sidebar.match(/aria-label=\{t\('Mở rộng thanh bên'\)\}/g) || []).length, 2);
  assert.equal((sidebar.match(/<Tooltip title=\{t\('Mở rộng thanh bên'\)\}/g) || []).length, 2);
  // The top one sits before the navigation list, and every toggle is at least 40px.
  assert.ok(sidebar.indexOf("aria-label={t('Mở rộng thanh bên')}") < sidebar.indexOf('{/* Navigation groups */}'));
  assert.ok((sidebar.match(/width: 40, height: 40/g) || []).length >= 2);
  assert.match(sidebar, /width: 40,\s*height: 40,\s*color: '#64748B'/);
});
