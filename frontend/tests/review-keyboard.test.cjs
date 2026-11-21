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

const { reviewShortcut, isTypingTarget, moveCriterionIndex } = loadTypeScriptModule('src/lib/reviewKeyboard.ts');

const ready = { canConfirm: true, canReject: true, canOpenPage: true, hasNextApplication: true };
const key = (name, extra = {}) => ({ key: name, ...extra });

test('j/k chuyển tiêu chí, n sang hồ sơ kế tiếp, Enter mở trang CV', () => {
  assert.equal(reviewShortcut(key('j'), ready, false), 'next-criterion');
  assert.equal(reviewShortcut(key('k'), ready, false), 'prev-criterion');
  assert.equal(reviewShortcut(key('n'), ready, false), 'next-application');
  assert.equal(reviewShortcut(key('Enter'), ready, false), 'open-page');
  assert.equal(reviewShortcut(key('J'), ready, false), 'next-criterion', 'chữ hoa vẫn là phím tắt');
});

test('1/2 chỉ có nghĩa khi tiêu chí đang chọn thực sự làm được', () => {
  assert.equal(reviewShortcut(key('1'), ready, false), 'confirm');
  assert.equal(reviewShortcut(key('2'), ready, false), 'reject');
  const noAction = { canConfirm: false, canReject: false, canOpenPage: false, hasNextApplication: false };
  assert.equal(reviewShortcut(key('1'), noAction, false), null);
  assert.equal(reviewShortcut(key('2'), noAction, false), null);
  assert.equal(reviewShortcut(key('Enter'), noAction, false), null);
  assert.equal(reviewShortcut(key('n'), noAction, false), null);
});

test('đang gõ chữ, có phím điều khiển hoặc sự kiện đã bị xử lý thì không chen vào', () => {
  assert.equal(reviewShortcut(key('1'), ready, true), null, 'ô lý do từ chối đang mở');
  assert.equal(reviewShortcut(key('j'), ready, true), null);
  assert.equal(reviewShortcut(key('n'), ready, true), null);
  assert.equal(reviewShortcut(key('1', { ctrlKey: true }), ready, false), null);
  assert.equal(reviewShortcut(key('j', { metaKey: true }), ready, false), null);
  assert.equal(reviewShortcut(key('n', { altKey: true }), ready, false), null);
  assert.equal(reviewShortcut(key('1', { defaultPrevented: true }), ready, false), null);
});

test('phím khác không bị nuốt', () => {
  for (const other of ['a', 'Tab', 'Escape', ' ', 'ArrowDown', '3']) {
    assert.equal(reviewShortcut(key(other), ready, false), null, `${other} phải để trình duyệt xử lý`);
  }
});

test('nhận ra ô nhập để không biến chữ trong ghi chú thành lệnh', () => {
  assert.equal(isTypingTarget({ tagName: 'INPUT' }), true);
  assert.equal(isTypingTarget({ tagName: 'textarea' }), true);
  assert.equal(isTypingTarget({ tagName: 'SELECT' }), true);
  assert.equal(isTypingTarget({ tagName: 'DIV', isContentEditable: true }), true);
  assert.equal(isTypingTarget({ tagName: 'BUTTON' }), false);
  assert.equal(isTypingTarget(null), false);
  assert.equal(isTypingTarget('input'), false);
});

test('chuyển tiêu chí dừng ở hai đầu, không quay vòng', () => {
  assert.equal(moveCriterionIndex(0, 3, 1), 1);
  assert.equal(moveCriterionIndex(2, 3, 1), 2, 'tiêu chí cuối không nhảy về đầu');
  assert.equal(moveCriterionIndex(0, 3, -1), 0, 'tiêu chí đầu không nhảy về cuối');
  assert.equal(moveCriterionIndex(2, 3, -1), 1);
  assert.equal(moveCriterionIndex(-1, 3, 1), 1, 'chưa chọn gì thì j bắt đầu từ tiêu chí đầu');
  assert.equal(moveCriterionIndex(0, 0, 1), -1);
});

const { nextPendingCriterionId } = loadTypeScriptModule('src/lib/reviewKeyboard.ts');

test('xác nhận xong thì đi tiếp tiêu chí còn chờ, không đứng lại ở tiêu chí vừa xong', () => {
  const results = [
    { criterion_id: 'c2', result_id: 'r-c2', requires_verification: true, hr_reviews: [] },
    { criterion_id: 'c3', result_id: 'r-c3', requires_verification: true, hr_reviews: [] },
    { criterion_id: 'c4', result_id: 'r-c4', requires_verification: true, hr_reviews: [] },
  ];
  assert.equal(nextPendingCriterionId(results, 'c2'), 'c3');
  assert.equal(nextPendingCriterionId(results, 'c3'), 'c4');
});

test('hết việc phía trước thì quay lại tiêu chí còn chờ phía trên thay vì bỏ sót', () => {
  const results = [
    { criterion_id: 'c2', result_id: 'r-c2', requires_verification: true, hr_reviews: [] },
    { criterion_id: 'c3', result_id: 'r-c3', requires_verification: true, hr_reviews: [] },
  ];
  assert.equal(nextPendingCriterionId(results, 'c3'), 'c2');
});

test('bỏ qua tiêu chí đã xác minh, không cần xác minh, hoặc không có kết quả để ghi', () => {
  const results = [
    { criterion_id: 'c1', result_id: 'r-c1', requires_verification: false, hr_reviews: [] },
    { criterion_id: 'c2', result_id: 'r-c2', requires_verification: true, hr_reviews: [] },
    { criterion_id: 'c3', result_id: 'r-c3', requires_verification: true, hr_reviews: [{ decision: 'CONFIRMED' }] },
    { criterion_id: 'c4', result_id: null, requires_verification: true, hr_reviews: [] },
    { criterion_id: 'c5', result_id: 'r-c5', requires_verification: true, hr_reviews: [] },
  ];
  assert.equal(nextPendingCriterionId(results, 'c2'), 'c5', 'c1/c3/c4 không phải việc còn lại');
  assert.equal(nextPendingCriterionId(results, 'c1'), 'c2', 'tiêu chí không cần xác minh không phải điểm dừng');
});

test('không còn tiêu chí chờ thì không nhảy đi đâu', () => {
  const results = [
    { criterion_id: 'c2', result_id: 'r-c2', requires_verification: true, hr_reviews: [{ decision: 'CONFIRMED' }] },
  ];
  assert.equal(nextPendingCriterionId(results, 'c2'), null);
  assert.equal(nextPendingCriterionId([], 'c2'), null);
});
