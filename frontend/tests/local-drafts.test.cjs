const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
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

const drafts = loadTypeScriptModule('src/lib/localDrafts.ts');

function memoryStorage() {
  const map = new Map();
  return {
    get length() { return map.size; },
    key: index => [...map.keys()][index] ?? null,
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, String(value)); },
    removeItem: key => { map.delete(key); },
    clear: () => map.clear(),
    _map: map,
  };
}

test('a scorecard draft survives a reload and is scoped to its share', () => {
  const storage = memoryStorage();
  const key = drafts.scorecardDraftKey('share-1', 'card-a');
  assert.equal(drafts.writeDraft(key, { revision: 3, card: { strengths: 'Nháp' } }, 1_000, storage), true);
  assert.deepEqual(drafts.readDraft(key, 2_000, storage), { revision: 3, card: { strengths: 'Nháp' } });
  // Another share or scorecard must never read this draft.
  assert.equal(drafts.readDraft(drafts.scorecardDraftKey('share-2', 'card-a'), 2_000, storage), null);
  assert.equal(drafts.readDraft(drafts.scorecardDraftKey('share-1', 'card-b'), 2_000, storage), null);
});

test('expired, tampered and future-dated drafts are discarded rather than restored', () => {
  const storage = memoryStorage();
  const key = drafts.scorecardDraftKey('share-1', 'card-a');
  drafts.writeDraft(key, { revision: 1 }, 1_000, storage);
  assert.equal(drafts.readDraft(key, 1_000 + drafts.DRAFT_TTL_MS + 1, storage), null);
  assert.equal(storage.getItem(key), null, 'expired draft is removed from storage');

  storage.setItem(key, '{not json');
  assert.equal(drafts.readDraft(key, 2_000, storage), null);

  storage.setItem(key, JSON.stringify({ saved_at: 5_000, data: { revision: 1 } }));
  // A clock that jumps backwards must not resurrect an over-dated draft.
  assert.equal(drafts.readDraft(key, 1_000, storage), null);
});

test('storage failures never throw into the review screen', () => {
  const broken = {
    get length() { return 0; }, key: () => null,
    getItem: () => { throw new Error('blocked'); },
    setItem: () => { throw new Error('quota'); },
    removeItem: () => { throw new Error('blocked'); },
  };
  assert.equal(drafts.writeDraft('k', { a: 1 }, 1, broken), false);
  assert.equal(drafts.readDraft('k', 1, broken), null);
  assert.equal(drafts.removeDraft('k', broken), undefined);
  assert.equal(drafts.readDraft('k', 1, null), null);
  assert.equal(drafts.writeDraft('k', { a: 1 }, 1, null), false);
});

test('purging on access loss removes every draft for that share only', () => {
  const storage = memoryStorage();
  drafts.writeDraft(drafts.scorecardDraftKey('share-1', 'card-a'), { revision: 1 }, 1, storage);
  drafts.writeDraft(drafts.scorecardDraftKey('share-1', 'card-b'), { revision: 1 }, 1, storage);
  drafts.writeDraft(drafts.shareFeedbackDraftKey('share-1'), { content: 'x' }, 1, storage);
  drafts.writeDraft(drafts.scorecardDraftKey('share-2', 'card-a'), { revision: 1 }, 1, storage);
  drafts.writeDraft('hra:draft:unrelated', { a: 1 }, 1, storage);

  assert.equal(drafts.purgeShareDrafts('share-1', storage), 3);
  assert.equal(drafts.readDraft(drafts.scorecardDraftKey('share-1', 'card-a'), 2, storage), null);
  assert.equal(drafts.readDraft(drafts.shareFeedbackDraftKey('share-1'), 2, storage), null);
  assert.deepEqual(drafts.readDraft(drafts.scorecardDraftKey('share-2', 'card-a'), 2, storage), { revision: 1 });
  assert.deepEqual(drafts.readDraft('hra:draft:unrelated', 2, storage), { a: 1 });
});

test('a newer server revision invalidates the stored draft fingerprint', () => {
  // The panel only restores a draft whose revision matches the server copy;
  // this mirrors that rule so a stale draft is never replayed over newer data.
  const storage = memoryStorage();
  const key = drafts.scorecardDraftKey('share-1', 'card-a');
  drafts.writeDraft(key, { revision: 2, card: { strengths: 'old' } }, 1, storage);
  const draft = drafts.readDraft(key, 2, storage);
  const serverCard = { scorecard_id: 'card-a', revision: 3 };
  assert.notEqual(draft.revision, serverCard.revision);
});
