const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

test('generated admin SDK binds pagination, account ID, typed JSON and session revocation', () => {
  const calls = [];
  const source = fs.readFileSync('lib/api/generated/services/AdminService.ts', 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } });
  const context = { exports: {}, require: name => name.endsWith('/request')
    ? { request: (_, options) => { calls.push(options); return options; } }
    : { OpenAPI: {} } };
  vm.runInNewContext(compiled.outputText, context);
  const { AdminService } = context.exports;
  const create = { username: 'new-user', password: 'test-input-only', role: 'user' };
  AdminService.listAccounts(10, 20);
  AdminService.createAccount(create);
  AdminService.setAccountActive('id', { active: false });
  AdminService.resetAccountPassword('id', { password: 'test-input-only' });
  AdminService.revokeAccountSessions('id', {});
  assert.equal(calls[0].query.limit, 10);
  assert.equal(calls[0].query.offset, 20);
  assert.equal(calls[1].body, create);
  assert.equal(calls[2].method, 'PATCH');
  assert.equal(calls[2].path.user_id, 'id');
  assert.equal(calls[3].url, '/admin/users/{user_id}/password');
  assert.equal(calls[4].url, '/admin/users/{user_id}/sessions/revoke');
  assert.equal(calls[4].method, 'POST');
  for (const call of calls.slice(1)) assert.equal(call.mediaType, 'application/json');
});
