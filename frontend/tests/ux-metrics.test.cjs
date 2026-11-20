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

const metrics = loadTypeScriptModule('src/lib/uxMetrics.ts');
const {
  recordUxEvent, readUxEvents, clearUxEvents, summarizeUxImpact,
  UX_METRICS_STORAGE_KEY, UX_METRICS_MAX_EVENTS,
} = metrics;

function fakeStorage(initial) {
  const data = new Map(initial ? [[UX_METRICS_STORAGE_KEY, initial]] : []);
  return {
    data,
    getItem: key => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => { data.set(key, value); },
    removeItem: key => { data.delete(key); },
  };
}

const T0 = Date.UTC(2026, 10, 19, 8, 0, 0);
const minutes = n => T0 + n * 60_000;

test('mỗi event được ghi nối tiếp và chỉ giữ số gần nhất', () => {
  const storage = fakeStorage();
  for (let i = 0; i < UX_METRICS_MAX_EVENTS + 10; i += 1) {
    recordUxEvent({ type: 'PROFILE_OPENED', at: T0 + i, application_id: `app-${i}` }, storage);
  }
  const events = readUxEvents(storage);
  assert.equal(events.length, UX_METRICS_MAX_EVENTS);
  assert.equal(events.at(-1).application_id, `app-${UX_METRICS_MAX_EVENTS + 9}`);
  assert.equal(events[0].application_id, `app-${10}`);
  assert.equal(storage.data.size, 1, 'chỉ một khoá storage, không phình thêm khoá');
});

test('dữ liệu hỏng hoặc lạ bị bỏ qua thay vì dựng số đo giả', () => {
  assert.deepEqual(readUxEvents(fakeStorage('{not json')), []);
  assert.deepEqual(readUxEvents(fakeStorage('{"type":"PROFILE_OPENED"}')), []);
  const mixed = JSON.stringify([
    { type: 'PROFILE_OPENED', at: T0 },
    { type: 'CLICKED_SOMETHING', at: T0 + 1 },
    { type: 'PROFILE_CLOSED', at: -5 },
    { type: 'PROFILE_CLOSED', at: T0 + 2, duration_ms: 1000 },
  ]);
  const events = readUxEvents(fakeStorage(mixed));
  assert.equal(events.length, 2);
  assert.equal(events[1].duration_ms, 1000);
});

test('chỉ lưu id hồ sơ và thời lượng, không lưu tên hay nội dung', () => {
  const storage = fakeStorage();
  recordUxEvent({ type: 'PROFILE_OPENED', at: T0, application_id: 'app-1', candidate_name: 'Nguyễn A', cv_text: 'bí mật' }, storage);
  const [event] = readUxEvents(storage);
  assert.deepEqual(Object.keys(event).sort(), ['application_id', 'at', 'type']);
  assert.doesNotMatch(storage.getItem(UX_METRICS_STORAGE_KEY), /Nguyễn A|bí mật/);
});

test('trung vị thời gian ở trong hồ sơ, không bị lệch bởi một lượt dài nhưng còn trong ngưỡng', () => {
  const events = [
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'a', duration_ms: 60_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'b', duration_ms: 120_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'c', duration_ms: 240_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'd', duration_ms: 600_000 },
  ];
  const summary = summarizeUxImpact(events);
  assert.equal(summary.profileCloses, 4);
  assert.equal(summary.ignoredDwellCount, 0);
  assert.equal(summary.medianDwellMinutes, 3); // (2 + 4) / 2 phút
});

test('tab để quên qua đêm bị loại khỏi trung vị thay vì kéo trung vị lên', () => {
  const events = [
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'a', duration_ms: 60_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'b', duration_ms: 120_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'c', duration_ms: 180_000 },
    // Mở hồ sơ rồi để tab qua đêm: 9 tiếng, không phải thời gian xem thật.
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'd', duration_ms: 9 * 3_600_000 },
  ];
  const summary = summarizeUxImpact(events);
  assert.equal(summary.profileCloses, 4, 'lượt bị loại vẫn là một lượt đã rời hồ sơ');
  assert.equal(summary.ignoredDwellCount, 1);
  // Nếu tính cả lượt qua đêm thì trung vị thành 2,5 phút và một lần quên đã làm
  // sai số đo; chỉ ba lượt hợp lý còn lại cho trung vị 2 phút.
  assert.equal(summary.medianDwellMinutes, 2);
});

test('đúng ngưỡng vẫn được tính, và mọi lượt đều quá dài thì trung vị là null', () => {
  const atCap = summarizeUxImpact([
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'a', duration_ms: 30 * 60_000 },
  ]);
  assert.equal(atCap.ignoredDwellCount, 0);
  assert.equal(atCap.medianDwellMinutes, 30);
  const allTooLong = summarizeUxImpact([
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'a', duration_ms: 8 * 3_600_000 },
    { type: 'PROFILE_CLOSED', at: T0, application_id: 'b', duration_ms: 12 * 3_600_000 },
  ]);
  assert.equal(allTooLong.profileCloses, 2);
  assert.equal(allTooLong.ignoredDwellCount, 2);
  assert.equal(allTooLong.medianDwellMinutes, null, 'không có lượt nào để tính thì không bịa ra số');
});

test('thời gian hoàn tất tính từ lần mở hồ sơ đầu tiên, không phải lần mở lại', () => {
  const events = [
    { type: 'PROFILE_OPENED', at: minutes(0), application_id: 'app-1' },
    { type: 'PROFILE_OPENED', at: minutes(9), application_id: 'app-1' },
    { type: 'VERIFICATION_COMPLETED', at: minutes(10), application_id: 'app-1' },
    { type: 'PROFILE_OPENED', at: minutes(0), application_id: 'app-2' },
    { type: 'VERIFICATION_COMPLETED', at: minutes(20), application_id: 'app-2' },
    // Hoàn tất không có lần mở trước đó thì không được ghép bừa.
    { type: 'VERIFICATION_COMPLETED', at: minutes(5), application_id: 'app-3' },
  ];
  const summary = summarizeUxImpact(events);
  assert.equal(summary.verifiedProfiles, 3, 'ba hồ sơ khác nhau đã hoàn tất');
  assert.equal(summary.averageCompletionMinutes, 15); // (10 + 20) / 2
});

test('lô hành động: tổng hồ sơ, lỗi, tỉ lệ lỗi và thời gian trung bình', () => {
  const summary = summarizeUxImpact([
    { type: 'BULK_RUN', at: T0, duration_ms: 60_000, records: 10, failed: 1 },
    { type: 'BULK_RUN', at: T0, duration_ms: 180_000, records: 20, failed: 4 },
  ]);
  assert.equal(summary.bulkRuns, 2);
  assert.equal(summary.bulkRecords, 30);
  assert.equal(summary.bulkFailedRecords, 5);
  assert.equal(summary.bulkFailureRate, 0.167);
  assert.equal(summary.bulkAverageMinutes, 2);
});

test('chưa có event thì mọi số đo là null, không phải 0', () => {
  const summary = summarizeUxImpact([]);
  assert.equal(summary.medianDwellMinutes, null);
  assert.equal(summary.ignoredDwellCount, 0);
  assert.equal(summary.averageCompletionMinutes, null);
  assert.equal(summary.bulkFailureRate, null);
  assert.equal(summary.bulkAverageMinutes, null);
  assert.equal(summary.sampleSince, null);
  assert.equal(summary.bulkRuns, 0);
});

test('xoá số đo chỉ xoá khoá của module này', () => {
  const storage = fakeStorage();
  storage.setItem('hra_access_token', 'token');
  recordUxEvent({ type: 'BULK_RUN', at: T0, records: 1, failed: 0 }, storage);
  clearUxEvents(storage);
  assert.deepEqual(readUxEvents(storage), []);
  assert.equal(storage.getItem('hra_access_token'), 'token');
});

test('storage bị chặn không làm hỏng luồng gọi', () => {
  const throwing = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }, removeItem() { throw new Error('blocked'); } };
  assert.deepEqual(readUxEvents(throwing), []);
  assert.deepEqual(recordUxEvent({ type: 'PROFILE_OPENED', at: T0 }, throwing), []);
  assert.doesNotThrow(() => clearUxEvents(throwing));
});
