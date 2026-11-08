const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function generated(name, calls) {
  const source = fs.readFileSync(`lib/api/generated/services/${name}.ts`, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const context = { exports: {}, require: path => path.endsWith('/request')
    ? { request: (_, options) => { calls.push(options); return options; } } : { OpenAPI: {} } };
  vm.runInNewContext(compiled.outputText, context);
  return context.exports[name];
}

test('history SDK distinguishes persisted POST from original readonly GET and sends the request key', () => {
  const calls = [], History = generated('HistoryService', calls), Search = generated('SearchService', calls);
  const body = { q: 'fresh submitted question', k: 3, request_id: 'request-id', document_id: 'doc-id' };
  History.searchAndRecordHistory(body); Search.searchPages(body.q, 3, body.document_id);
  assert.equal(calls[0].method, 'POST'); assert.equal(calls[0].url, '/search'); assert.equal(calls[0].body, body);
  assert.equal(calls[0].mediaType, 'application/json'); assert.equal(calls[0].query, undefined);
  assert.equal(calls[1].method, 'GET'); assert.equal(calls[1].body, undefined);
  assert.equal(calls[1].query.q, body.q); assert.equal(calls[1].query.document_id, 'doc-id');
});

test('history SDK preserves version/confirmation and JSON body for DELETE, and uses owner-free list/detail', () => {
  const calls = [], History = generated('HistoryService', calls);
  const update = { version: 2, title: '本人标题', pinned: true }, removal = { version: 3, confirmed: true };
  History.listQueryHistory(10, 20); History.getQueryHistory('history-id');
  History.updateQueryHistory('history-id', update); History.deleteQueryHistory('history-id', removal);
  assert.equal(JSON.stringify(calls[0].query), JSON.stringify({ limit: 10, offset: 20 }));
  assert.equal(calls[1].url, '/history/{history_id}'); assert.equal(calls[1].path.history_id, 'history-id');
  assert.equal(calls[2].method, 'PATCH'); assert.equal(calls[2].body, update);
  assert.equal(calls[3].method, 'DELETE'); assert.equal(calls[3].body, removal);
  for (const call of calls.slice(2)) { assert.equal(call.path.history_id, 'history-id'); assert.equal(call.mediaType, 'application/json'); }
});

test('history mutations receive the shared in-memory CSRF header including DELETE', async () => {
  const api = {}, context = { exports: {}, require: () => ({ OpenAPI: api }) };
  const code = ts.transpileModule(fs.readFileSync('lib/api/client.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  vm.runInNewContext(code.outputText, context); context.exports.setCsrfToken('test-memory-token');
  for (const method of ['POST', 'PATCH', 'DELETE']) {
    const headers = await api.HEADERS({ method });
    assert.equal(headers['X-CSRF-Token'], 'test-memory-token'); assert.equal(headers['Content-Type'], 'application/json');
  }
  assert.equal((await api.HEADERS({ method: 'GET' }))['X-CSRF-Token'], undefined);
  context.exports.setCsrfToken(); assert.equal((await api.HEADERS({ method: 'DELETE' }))['X-CSRF-Token'], undefined);
  assert.equal(api.CREDENTIALS, 'same-origin');
});
