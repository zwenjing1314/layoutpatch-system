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
  const source = ts.transpileModule(fs.readFileSync('lib/use-deletion.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const context = { exports: {}, FormData: class { constructor(form) { this.data = { ...form.data }; } get(key) { return this.data[key] ?? null; } }, require(name) {
    if (name === 'react') return react;
    if (name === '@/lib/api/generated') return { DeletionService: service, ApiError };
    if (name === './workspace-lifecycle') return loadTs('lib/workspace-lifecycle.ts');
    if (name === './task-state') return loadTs('lib/task-state.ts');
    if (name === '@/lib/account-state') return loadTs('lib/account-state.ts');
    throw new Error('Unexpected dependency: ' + name);
  } };
  vm.runInNewContext(source, context);
  function render() {
    for (let count = 0; dirty || pending.length; count++) {
      assert.ok(count < 30, 'hook settled');
      if (dirty) { dirty = false; cursor = 0; result = context.exports.useDeletion(options); }
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
const target={document_id:'own-doc',display_name:'own',document_version_id:'version-1',access_version:3,status:'ready',cleanup_status:null,attempt:null};
const event=(data={})=>({preventDefault(){},currentTarget:{data}});
async function loaded(h,next_offset=null){h.panel;h.calls[0].resolve({items:[target],next_offset});await h.settle();}
test('deletion identity and leaving page cancel late list and write responses',async t=>{
 const h=harness({enabled:false});t.after(()=>h.close());h.panel;assert.equal(h.calls.length,0);h.update({enabled:true});const old=h.calls[0];h.update({userId:'different'});old.resolve({items:[target],next_offset:null});await h.settle();assert.equal(h.panel.response,null);assert.equal(old.cancelled,1);
 h.calls[1].resolve({items:[target],next_offset:null});await h.settle();h.panel.onOpen(target);const p=h.panel.onSubmit(event({confirmed:'yes'})),write=h.calls[2];h.update({enabled:false});write.resolve(target);await p;await h.settle();assert.equal(write.cancelled,1);assert.equal(h.panel.notice,'');assert.equal(h.panel.intent,null);assert.equal(h.changes.length,0);
});
test('delete requires confirmation and duplicate submission sends captured version once',async t=>{
 const h=harness();t.after(()=>h.close());await loaded(h);h.panel.onOpen(target);await h.panel.onSubmit(event());assert.equal(h.calls.length,1);assert.match(h.panel.error,/确认/);
 const submit=h.panel.onSubmit,p=submit(event({confirmed:'yes'}));await submit(event({confirmed:'yes'}));assert.equal(h.calls.length,2);assert.equal(h.calls[1].method,'deleteOwnDocument');assert.equal(JSON.stringify(h.calls[1].args),JSON.stringify(['own-doc',{document_version_id:'version-1',access_version:3,confirmed:true}]));h.calls[1].resolve({...target,status:'deleted'});await p;await h.settle();assert.match(h.panel.notice,/已撤销文档访问/);assert.equal(h.changes.length,1);assert.equal(h.panel.intent,null);
});
test('retry is bound to failed cleanup attempt; queued and completed cannot reopen',async t=>{
 const h=harness();t.after(()=>h.close());await loaded(h);for(const cleanup_status of ['queued','running','completed']){h.panel.onOpen({...target,status:'deleted',cleanup_status,attempt:2});assert.equal(h.panel.intent,null);}
 h.panel.onOpen({...target,status:'deleted',cleanup_status:'failed',attempt:2});const p=h.panel.onSubmit(event({confirmed:'yes'}));assert.equal(h.calls[1].method,'retryDocumentCleanup');assert.equal(JSON.stringify(h.calls[1].args),JSON.stringify(['own-doc',{attempt:2,confirmed:true}]));h.calls[1].resolve({...target,status:'deleted'});await p;await h.settle();assert.match(h.panel.notice,/文档仍不可读取/);
});
test('unknown and stale deletion never automatically retry and clear old retrieval',async t=>{
 for(const status of [409,503]){const h=harness();t.after(()=>h.close());await loaded(h);h.panel.onOpen(target);const p=h.panel.onSubmit(event({confirmed:'yes'}));h.calls[1].reject(new h.ApiError(status,'secret'));await p;await h.settle();assert.equal(h.changes.length,1);assert.ok(!h.panel.notice.includes('secret'));assert.equal(h.calls.filter(c=>c.method==='deleteOwnDocument').length,1);assert.match(h.panel.notice,status===409?/已变化/:/尚未确认/);}
});
test('deletion 401/403 reset private state before identity handling',async t=>{
 for(const status of [401,403]){const h=harness();t.after(()=>h.close());await loaded(h);h.panel.onOpen(target);const p=h.panel.onSubmit(event({confirmed:'yes'}));h.calls[1].reject(new h.ApiError(status));await p;await h.settle();assert.equal(h.sessionErrors.length,1);assert.equal(h.panel.response,null);assert.equal(h.panel.intent,null);}
});
test('deletion list paginates10 and restarts at zero on an empty later page',async t=>{
 const h=harness();t.after(()=>h.close());await loaded(h,10);h.panel.onNext();assert.equal(h.panel.offset,10);assert.deepEqual(h.calls[1].args,[10,10]);h.calls[1].resolve({items:[],next_offset:null});await h.settle();assert.equal(h.panel.offset,0);assert.deepEqual(h.calls[2].args,[10,0]);
});
