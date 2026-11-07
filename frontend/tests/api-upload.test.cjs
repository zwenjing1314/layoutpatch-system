const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

test('multipart keeps CSRF and lets fetch generate its boundary; auth writes stay JSON', async () => {
  const OpenAPI = {};
  const compiled = ts.transpileModule(fs.readFileSync('lib/api/client.ts', 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const context = { exports: {}, require: () => ({ OpenAPI }) };
  vm.runInNewContext(compiled.outputText, context);
  context.exports.setCsrfToken('test-csrf');
  const uploadHeaders = await OpenAPI.HEADERS({ method: 'POST', formData: { file: new Blob(['pdf']) } });
  const upload = new Request('http://localhost/api/index', {
    method: 'POST', headers: uploadHeaders, body: new FormData(),
  });
  assert.match(upload.headers.get('content-type'), /^multipart\/form-data; boundary=/);
  assert.equal(upload.headers.get('x-csrf-token'), 'test-csrf');
  const logout = await OpenAPI.HEADERS({ method: 'POST' });
  assert.equal(logout['Content-Type'], 'application/json');
  context.exports.setCsrfToken(undefined);
  assert.equal(Object.keys(await OpenAPI.HEADERS({ method: 'POST', formData: {} })).length, 0);
});
