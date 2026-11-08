const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

test('generated sharing SDK sends pagination and explicit version/epoch/confirmation JSON', () => {
  const calls = [];
  const compiled = ts.transpileModule(fs.readFileSync('lib/api/generated/services/SharingService.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const context = { exports: {}, require: name => name.endsWith('/request') ? { request: (_, options) => { calls.push(options); return options; } } : { OpenAPI: {} } };
  vm.runInNewContext(compiled.outputText, context);
  const { SharingService } = context.exports;
  const body = { document_version_id: 'version-id', access_version: 2, confirmed: true };
  SharingService.listSharingDocuments('literal_name', 10, 20); SharingService.publishDocument('doc-id', body); SharingService.unpublishDocument('doc-id', body);
  assert.equal(JSON.stringify(calls[0].query), JSON.stringify({ name: 'literal_name', limit: 10, offset: 20 }));
  assert.equal(calls[1].url, '/admin/documents/{document_id}/publish'); assert.equal(calls[2].url, '/admin/documents/{document_id}/unpublish');
  for (const call of calls.slice(1)) { assert.equal(call.path.document_id, 'doc-id'); assert.equal(call.body, body); assert.equal(call.method, 'POST'); assert.equal(call.mediaType, 'application/json'); }
});
