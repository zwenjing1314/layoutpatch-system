const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const { loadTs } = require('./load-workspace.cjs');

// A small hook scheduler tests the public hook contract without a DOM package.
// Browser checks separately exercise real React, native dialog and HTTP behavior.
function harness(initial = {}) {
  const slots = [], pending = [], calls = [], sessionErrors = [], changes = [];
  let cursor = 0, dirty = true, result;
  let options = { enabled: true, userId: 'self', csrfToken: 'csrf', onSessionError: e => sessionErrors.push(e), onChanged: () => changes.push(true), ...initial };
  const equal = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const react = {
    useState(value) {
      const index = cursor++;
      if (!slots[index]) slots[index] = { value: typeof value === 'function' ? value() : value };
      return [slots[index].value, next => { const value = typeof next === 'function' ? next(slots[index].value) : next; if (!Object.is(value, slots[index].value)) { slots[index].value = value; dirty = true; } }];
    },
    useRef(value) { const index = cursor++; if (!slots[index]) slots[index] = { current: value }; return slots[index]; },
    useCallback(callback, deps) { const index = cursor++; if (!slots[index] || !equal(slots[index].deps, deps)) slots[index] = { value: callback, deps }; return slots[index].value; },
    useEffect(callback, deps) { const index = cursor++; if (!slots[index] || !equal(slots[index].deps, deps)) pending.push({ index, callback, deps }); },
  };
  class ApiError extends Error { constructor(status, detail = '') { super('API'); this.status = status; this.body = { detail }; } }
  const service = new Proxy({}, { get: (_, method) => (...args) => {
    let resolve, reject;
    const promise = new Promise((a, b) => { resolve = a; reject = b; });
    const call = { method, args, resolve, reject, cancelled: 0 };
    promise.cancel = () => { call.cancelled++; }; // Intentionally allow a late resolution after cancellation.
    calls.push(call); return promise;
  } });
  const source = ts.transpileModule(fs.readFileSync('lib/use-sharing.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const context = { exports: {}, FormData: class { constructor(form) { this.data = { ...form.data }; } get(key) { return this.data[key] ?? null; } }, require(name) {
    if (name === 'react') return react;
    if (name === '@/lib/api/generated') return { SharingService: service, ApiError };
    if (name === './workspace-lifecycle') return loadTs('lib/workspace-lifecycle.ts');
    if (name === './task-state') return loadTs('lib/task-state.ts');
    if (name === '@/lib/account-state') return loadTs('lib/account-state.ts');
    throw new Error('Unexpected dependency: ' + name);
  } };
  vm.runInNewContext(source, context);
  function render() {
    for (let count = 0; dirty || pending.length; count++) {
      assert.ok(count < 30, 'hook settled');
      if (dirty) { dirty = false; cursor = 0; result = context.exports.useSharing(options); }
      const effects = pending.splice(0);
      for (const e of effects) slots[e.index]?.cleanup?.();
      for (const e of effects) slots[e.index] = { deps: e.deps, cleanup: e.callback() };
    }
    return result;
  }
  return { calls, sessionErrors, changes, ApiError,
    get panel() { return render().panel; }, get output() { return render(); },
    update(next) { options = { ...options, ...next }; dirty = true; return render(); },
    async settle() { for (let i = 0; i < 12; i++) { await Promise.resolve(); render(); } },
    close() { for (const slot of slots) slot?.cleanup?.(); },
  };
}
const target = { document_id: 'own-doc', display_name: 'own', document_version_id: 'version-1', version: 1, page_count: 12, visibility: 'private', access_version: 3, can_publish: true };
const event = (data = {}) => ({ preventDefault() {}, currentTarget: { data } });
async function loaded(h, next_offset = null) { h.panel; h.calls[0].resolve({ items: [target], next_offset }); await h.settle(); }

test('disabled management makes no request; identity change cancels and refuses a late list', async t => {
  const h = harness({ enabled: false }); t.after(() => h.close()); h.panel; assert.equal(h.calls.length, 0);
  h.update({ enabled: true }); const old = h.calls[0]; h.update({ userId: 'another-admin' });
  old.resolve({ items: [{ ...target, display_name: 'previous-private' }], next_offset: null }); await h.settle();
  assert.equal(old.cancelled, 1); assert.equal(h.panel.response, null);
  h.calls[1].resolve({ items: [target], next_offset: null }); await h.settle(); assert.equal(h.panel.response.items[0].display_name, 'own');
  h.output.reset(); assert.equal(h.panel.response, null); assert.equal(h.panel.intent, null);
});

test('explicit confirmation is required; synchronous duplicate publish sends captured version once', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen(target);
  await h.panel.onSubmit(event()); assert.equal(h.calls.length, 1); assert.match(h.panel.error, /确认/);
  const submit = h.panel.onSubmit, first = submit(event({ confirmed: 'yes' })), second = submit(event({ confirmed: 'yes' }));
  assert.equal(h.calls.length, 2); assert.equal(h.calls[1].method, 'publishDocument');
  assert.equal(JSON.stringify(h.calls[1].args), JSON.stringify(['own-doc', { document_version_id: 'version-1', access_version: 3, confirmed: true }]));
  assert.equal(h.panel.actionBusy, true);
  h.calls[1].resolve({ document: { ...target, visibility: 'shared', access_version: 4 }, changed: true });
  await first; await second; await h.settle(); assert.equal(h.panel.intent, null); assert.equal(h.panel.actionBusy, false);
  assert.match(h.panel.notice, /已发布共享/); assert.equal(h.changes.length, 1); assert.equal(h.calls.filter(c => c.method === 'listSharingDocuments').length, 2);
});

test('withdrawal uses the captured shared document and clears retrieval state for noop too', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen({ ...target, visibility: 'shared' });
  const pending = h.panel.onSubmit(event({ confirmed: 'yes' })); assert.equal(h.calls[1].method, 'unpublishDocument');
  h.calls[1].resolve({ document: target, changed: false }); await pending; await h.settle();
  assert.match(h.panel.notice, /没有重复修改授权版本/); assert.equal(h.changes.length, 1);
});

test('leaving sharing rejects late mutation success and clears dialog, list and notices', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen(target);
  const pending = h.panel.onSubmit(event({ confirmed: 'yes' })), write = h.calls[1]; h.update({ enabled: false });
  write.resolve({ document: target, changed: true }); await pending; await h.settle();
  assert.equal(write.cancelled, 1); assert.equal(h.panel.response, null); assert.equal(h.panel.intent, null); assert.equal(h.panel.notice, ''); assert.equal(h.changes.length, 0);
});

test('stale and unknown outcomes never retry writes or echo server text and invalidate old results', async t => {
  for (const status of [409, 503]) {
    const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen(target);
    const pending = h.panel.onSubmit(event({ confirmed: 'yes' })); h.calls[1].reject(new h.ApiError(status, 'secret-response-content'));
    await pending; await h.settle(); assert.equal(h.changes.length, 1); assert.ok(!h.panel.notice.includes('secret'));
    assert.match(h.panel.notice, status === 409 ? /授权版本已变化/ : /尚未确认/); assert.equal(h.calls.filter(c => c.method === 'publishDocument').length, 1);
    assert.equal(h.panel.intent, null);
  }
});

test('401 and 403 clear sharing before identity handling', async t => {
  for (const status of [401, 403]) {
    const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen(target);
    const pending = h.panel.onSubmit(event({ confirmed: 'yes' })); h.calls[1].reject(new h.ApiError(status));
    await pending; await h.settle(); assert.equal(h.sessionErrors.length, 1); assert.equal(h.panel.response, null); assert.equal(h.panel.intent, null); assert.equal(h.panel.notice, '');
  }
});

test('pagination follows next_offset and empty later pages restart at zero', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h, 10); h.panel.onNext();
  assert.equal(h.panel.offset, 10); assert.deepEqual(h.calls[1].args, ['', 10, 10]);
  h.calls[1].resolve({ items: [], next_offset: null }); await h.settle();
  assert.equal(h.panel.offset, 0); assert.deepEqual(h.calls[2].args, ['', 10, 0]);
});
