const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const { loadTs } = require('./load-workspace.cjs');

// A small hook scheduler tests the public hook contract without a DOM package.
// Browser checks separately exercise real React, native dialog and HTTP behavior.
function harness(initial = {}) {
  const slots = [], pending = [], calls = [], sessionErrors = [], selfChanges = [];
  let cursor = 0, dirty = true, result;
  let options = { enabled: true, userId: 'self', csrfToken: 'csrf', onSessionError: e => sessionErrors.push(e), onSelfChanged: (...args) => selfChanges.push(args), ...initial };
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
  const source = ts.transpileModule(fs.readFileSync('lib/use-accounts.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const context = { exports: {}, FormData: class { constructor(form) { this.data = { ...form.data }; } get(key) { return this.data[key] ?? null; } }, require(name) {
    if (name === 'react') return react;
    if (name === '@/lib/api/generated') return { AdminService: service, ApiError };
    if (name === '@/lib/workspace-lifecycle') return loadTs('lib/workspace-lifecycle.ts');
    if (name === '@/lib/task-state') return loadTs('lib/task-state.ts');
    if (name === '@/lib/account-state') return loadTs('lib/account-state.ts');
    throw new Error('Unexpected dependency: ' + name);
  } };
  vm.runInNewContext(source, context);
  function render() {
    for (let count = 0; dirty || pending.length; count++) {
      assert.ok(count < 30, 'hook settled');
      if (dirty) { dirty = false; cursor = 0; result = context.exports.useAccounts(options); }
      const effects = pending.splice(0);
      for (const e of effects) slots[e.index]?.cleanup?.();
      for (const e of effects) slots[e.index] = { deps: e.deps, cleanup: e.callback() };
    }
    return result;
  }
  return { calls, sessionErrors, selfChanges, ApiError,
    get panel() { return render().panel; }, get output() { return render(); },
    update(next) { options = { ...options, ...next }; dirty = true; return render(); },
    async settle() { for (let i = 0; i < 12; i++) { await Promise.resolve(); render(); } },
    close() { for (const slot of slots) slot?.cleanup?.(); },
  };
}
const target = { user_id: 'other', username: 'other', role: 'user', active: true };
function event(data = {}) {
  const fields = [{ value: data.password || '' }, { value: data.confirm_password || '' }];
  return { fields, preventDefault() {}, currentTarget: { data, querySelectorAll() { return fields; } } };
}
async function loaded(h) { h.panel; h.calls[0].resolve({ items: [target], next_offset: null }); await h.settle(); }

test('ordinary/hidden management makes no list request; identity change refuses a late list', async t => {
  const h = harness({ enabled: false }); t.after(() => h.close());
  h.panel; assert.equal(h.calls.length, 0);
  h.update({ enabled: true }); const old = h.calls[0];
  h.update({ userId: 'new-admin' }); assert.equal(old.cancelled, 1);
  old.resolve({ items: [{ ...target, username: 'private-old-list' }], next_offset: null }); await h.settle();
  assert.equal(h.panel.accounts, null);
  h.calls[1].resolve({ items: [target], next_offset: null }); await h.settle();
  assert.equal(h.panel.accounts.items[0].username, 'other');
  h.output.reset(); assert.equal(h.panel.accounts, null); assert.equal(h.panel.intent, null);
});

test('synchronous duplicate submits create one write, erase password inputs and refresh once', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h);
  h.panel.onOpen('create'); const submit = h.panel.onSubmit;
  const password = 'isolated-secret-password';
  const input = event({ username: 'new-user', role: 'user', password, confirm_password: password, confirmed: 'yes' });
  const first = submit(input), second = submit(input);
  assert.equal(h.calls.filter(c => c.method === 'createAccount').length, 1);
  assert.ok(input.fields.every(v => v.value === ''));
  assert.ok(!JSON.stringify(h.panel).includes(password));
  assert.equal(h.panel.actionBusy, true);
  h.calls[1].resolve({ account: target, changed: true }); await first; await second; await h.settle();
  assert.equal(h.panel.actionBusy, false); assert.equal(h.panel.intent, null);
  assert.match(h.panel.notice, /创建账号成功/);
  assert.equal(h.calls.filter(c => c.method === 'listAccounts').length, 2);
});

test('confirmation and matching passwords are required before any credential write', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h);
  h.panel.onOpen('reset', target);
  for (const data of [{ password: 'long-secret-password', confirm_password: 'long-secret-password' }, { confirmed: 'yes', password: 'long-secret-password', confirm_password: 'different-secret-password' }]) {
    const input = event(data); await h.panel.onSubmit(input); await h.settle();
    assert.ok(input.fields.every(v => !v.value)); assert.ok(h.panel.dialogError);
    assert.equal(h.calls.length, 1);
  }
});

test('reset sends only the new password; enable sends strict active state through the SDK', async t => {
  for (const action of ['reset', 'enable']) {
    const h = harness(); t.after(() => h.close()); await loaded(h);
    h.panel.onOpen(action, target);
    const password = 'new-isolated-password';
    const pending = h.panel.onSubmit(event({ confirmed: 'yes', password, confirm_password: password }));
    const write = h.calls[1];
    assert.equal(write.method, action === 'reset' ? 'resetAccountPassword' : 'setAccountActive');
    assert.equal(write.args[0], target.user_id);
    assert.equal(JSON.stringify(write.args[1]), JSON.stringify(action === 'reset' ? { password } : { active: true }));
    assert.ok(!JSON.stringify(h.panel).includes(password));
    write.resolve({ account: target, changed: true }); await pending; await h.settle();
    assert.match(h.panel.notice, /成功/); assert.equal(h.panel.intent, null);
  }
});

test('leaving management cancels waiting and rejects a late successful mutation', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h);
  h.panel.onOpen('revoke', target); const pending = h.panel.onSubmit(event({ confirmed: 'yes' }));
  const write = h.calls[1]; h.update({ enabled: false });
  write.resolve({ account: target, changed: true }); await pending; await h.settle();
  assert.equal(write.cancelled, 1); assert.equal(h.panel.notice, ''); assert.equal(h.panel.accounts, null); assert.equal(h.panel.intent, null);
  assert.equal(h.calls.length, 2); assert.equal(h.selfChanges.length, 0);
});

test('business rejection is explicit; lost write outcome is never automatically retried', async t => {
  const h = harness(); t.after(() => h.close()); await loaded(h);
  h.panel.onOpen('disable', { ...target, user_id: 'self' });
  const rejected = h.panel.onSubmit(event({ confirmed: 'yes' })); h.calls[1].reject(new h.ApiError(409, 'LAST_ACTIVE_ADMIN'));
  await rejected; await h.settle(); assert.match(h.panel.notice, /最后一个/); assert.equal(h.selfChanges.length, 0);
  h.calls[2].resolve({ items: [target], next_offset: null }); await h.settle();
  h.panel.onOpen('revoke', target);
  const lost = h.panel.onSubmit(event({ confirmed: 'yes' })); h.calls[3].reject(new Error('offline-secret-body'));
  await lost; await h.settle();
  assert.match(h.panel.notice, /尚未确认/); assert.ok(!h.panel.notice.includes('secret'));
  assert.equal(h.calls.filter(c => c.method === 'revokeAccountSessions').length, 1);
});

test('self revoke clears state and delegates full workspace lock; uncertain self result rechecks identity', async t => {
  for (const uncertain of [false, true]) {
    const h = harness(); t.after(() => h.close()); await loaded(h);
    h.panel.onOpen('revoke', { ...target, user_id: 'self' }); const pending = h.panel.onSubmit(event({ confirmed: 'yes' }));
    if (uncertain) h.calls[1].reject(new Error('connection-lost'));
    else h.calls[1].resolve({ account: target, changed: true });
    await pending; await h.settle();
    assert.deepEqual(h.selfChanges, [['revoke', uncertain]]); assert.equal(h.panel.accounts, null); assert.equal(h.panel.intent, null);
    assert.equal(h.calls.length, 2);
  }
});

test('401 and 403 responses clear private management state before notifying the parent', async t => {
  for (const status of [401, 403]) {
    const h = harness(); t.after(() => h.close()); await loaded(h); h.panel.onOpen('disable', target);
    const pending = h.panel.onSubmit(event({ confirmed: 'yes' })); h.calls[1].reject(new h.ApiError(status));
    await pending; await h.settle();
    assert.equal(h.sessionErrors.length, 1); assert.equal(h.panel.accounts, null); assert.equal(h.panel.intent, null); assert.equal(h.panel.notice, '');
  }
});

test('pagination uses server next_offset and an emptied later page returns to first page', async t => {
  const h = harness(); t.after(() => h.close()); h.panel;
  h.calls[0].resolve({ items: [target], next_offset: 10 }); await h.settle();
  h.panel.onNext(); assert.equal(h.panel.offset, 10); assert.deepEqual(h.calls[1].args, [10, 10]);
  h.calls[1].resolve({ items: [], next_offset: null }); await h.settle();
  assert.equal(h.panel.offset, 0); assert.deepEqual(h.calls[2].args, [10, 0]);
});
