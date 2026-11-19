const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');

const base = process.env.HRA_E2E_BASE_URL;
if (!base || !['localhost', '127.0.0.1', '[::1]'].includes(new URL(base).hostname)) {
  throw Error('Use a local disposable Next.js server.');
}
const json = (r, body, status = 200) => r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

const PHRASE = 'XOA DU LIEU TEST';

const SCOPES = [
  { code: 'CV', label: 'Hồ sơ ứng viên và CV', description: 'Toàn bộ hồ sơ ứng tuyển và tài liệu CV.', pulls_in: [] },
  { code: 'JD', label: 'JD và rubric', description: 'JD và phiên bản tiêu chí.', pulls_in: ['POSITIONS'] },
  { code: 'POSITIONS', label: 'Vị trí tuyển dụng', description: 'Vị trí và phân công.', pulls_in: ['JD'] },
  { code: 'OPERATIONS', label: 'Vận hành và kiểm toán', description: 'Operation và log kiểm toán.', pulls_in: [] },
];

const PREVIEW = {
  requested_scopes: ['JD'],
  effective_scopes: ['JD', 'POSITIONS'],
  implied_scopes: ['POSITIONS'],
  tables: [
    { name: 'positions', rows: 6 },
    { name: 'jd_versions', rows: 8 },
    { name: 'criteria_versions', rows: 9 },
  ],
  total_rows: 23,
  storage: { buckets: [], objects: 0, note: '' },
  protected: [{ table: 'user_profiles', rows: 5 }, { table: 'departments', rows: 2 }],
};

// Dọn dữ liệu test: ba chốt an toàn phải giữ được, kể cả khi người dùng cố bấm.
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.HRA_E2E_CHROMIUM_EXECUTABLE,
    args: JSON.parse(process.env.HRA_E2E_CHROMIUM_ARGS || '[]'),
  });
  const c = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  await c.addInitScript(() => { localStorage.setItem('hra_access_token', 'test'); localStorage.setItem('hra_locale', 'vi'); });

  const calls = { preview: 0, execute: [] };
  await c.route('**/v1/**', async r => {
    const p = new URL(r.request().url()).pathname;
    const method = r.request().method();
    if (p === '/v1/auth/me') return json(r, { user_id: 'admin', display_name: 'Admin', system_roles: ['ADMIN'], position_assignments: [] });
    if (p === '/v1/admin/test-data/scopes') return json(r, { scopes: SCOPES, confirmation_phrase: PHRASE, protected_tables: ['user_profiles', 'departments'] });
    if (p === '/v1/admin/test-data/preview' && method === 'POST') {
      calls.preview += 1;
      return json(r, PREVIEW);
    }
    if (p === '/v1/admin/test-data/execute' && method === 'POST') {
      const body = r.request().postDataJSON();
      calls.execute.push(body);
      return json(r, {
        effective_scopes: body.scopes,
        rows_deleted: { positions: 6, jd_versions: 8, criteria_versions: 9 },
        rows_total: 23,
        skipped_tables: [],
        storage: { skipped: true },
        storage_error: null,
      });
    }
    return json(r, {});
  });

  const page = await c.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`${base}/admin`, { waitUntil: 'networkidle' });

  // Mở tab "Dọn dữ liệu test".
  await page.getByRole('tab', { name: 'Dọn dữ liệu test' }).click();
  await page.getByTestId('test-data-purge').waitFor();

  // Chốt 1: chưa chọn gì thì không xem trước được.
  const previewButton = page.getByTestId('purge-preview-button');
  assert.equal(await previewButton.isDisabled(), true, 'Nút xem trước phải tắt khi chưa chọn nhóm nào');

  // Chốt 2: nút xoá phải tắt trước khi xem trước, dù đã gõ đúng chuỗi.
  const executeButton = page.getByTestId('purge-execute-button');
  assert.equal(await executeButton.isDisabled(), true, 'Nút xoá phải tắt trước bước xem trước');

  // Chọn JD — phải hiện cảnh báo "kéo theo Vị trí".
  await page.getByRole('checkbox', { name: 'JD và rubric' }).check();
  await page.getByText('Kéo theo: Vị trí tuyển dụng').waitFor();

  await previewButton.click();
  await page.getByTestId('purge-preview-table').waitFor();
  assert.equal(calls.preview, 1, 'Chỉ được gọi preview một lần');
  await page.getByText('A total of 23 rows across 3 tables will be deleted.').or(
    page.getByText('Tổng cộng 23 dòng trong 3 bảng sẽ bị xoá.')
  ).first().waitFor();

  // Phạm vi thực tế mở rộng phải được BÁO RA, không im lặng xoá thêm.
  await page.getByText(/không tách rời được/).waitFor();

  // Cái không mất phải hiện rõ.
  await page.getByText('Những thứ KHÔNG bị xoá:').waitFor();

  // Chốt 3: gõ sai/thiếu thì nút xoá vẫn tắt.
  const input = page.getByTestId('purge-confirm-input');
  await input.fill('XOA DU LIEU');
  assert.equal(await executeButton.isDisabled(), true, 'Chuỗi chưa khớp thì nút xoá phải tắt');
  await page.getByText(/Chuỗi chưa khớp/).waitFor();

  // Gõ đúng (kèm khoảng trắng thừa — phải chấp nhận).
  await input.fill(`  ${PHRASE}  `);
  assert.equal(await executeButton.isDisabled(), false, 'Gõ đúng chuỗi thì nút xoá phải bật');

  await executeButton.click();
  await page.getByTestId('purge-result').waitFor();
  await page.getByText('Đã xoá 23 dòng.').waitFor();

  assert.equal(calls.execute.length, 1, 'Chỉ được gọi execute một lần');
  assert.deepEqual(calls.execute[0].scopes, ['JD'], 'Chỉ gửi phạm vi người dùng chọn; server tự mở rộng');
  assert.equal(calls.execute[0].confirmation.trim(), PHRASE, 'Phải gửi chuỗi xác nhận');

  // Đổi phạm vi sau khi xem trước phải làm mất hiệu lực preview cũ.
  await page.getByRole('checkbox', { name: 'Hồ sơ ứng viên và CV' }).check();
  assert.equal(await page.getByTestId('purge-preview-table').count(), 0, 'Preview cũ phải biến mất khi đổi phạm vi');
  assert.equal(await page.getByTestId('purge-execute-button').isDisabled(), true, 'Đổi phạm vi phải tắt lại nút xoá');

  assert.deepEqual(errors, [], `Không được có lỗi runtime: ${errors.join('; ')}`);
  await browser.close();
  console.log('purge e2e: OK');
})();
