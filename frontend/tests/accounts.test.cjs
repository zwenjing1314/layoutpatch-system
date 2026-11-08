const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { AccountsPanel, AccountActionDialog } = loadTs('components/workspace/accounts.tsx');
const { WorkspaceShell } = loadTs('components/workspace/workspace.tsx');
const { accountFailure, accountImpact } = loadTs('lib/account-state.ts');
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const account = { user_id: 'admin-id', username: 'name<script>&', role: 'admin', active: true, must_change_password: false, created_at: '2026-11-08T00:00:00Z', updated_at: '2026-11-08T00:00:00Z' };
const panel = { userId: account.user_id, accounts: { items: [account], next_offset: 10 }, offset: 0, listBusy: false, listError: '', notice: '', intent: null, dialogKey: 0, dialogError: '', actionBusy: false, onRefresh() {}, onPrevious() {}, onNext() {}, onOpen() {}, onClose() {}, onSubmit() {} };
const workspace = { username: 'A', role: 'user', question: '', submittedQuestion: '', busy: false, notice: '', result: null, selected: null, image: null, imageBusy: false, imageError: '', searchMode: 'library', targetDocument: null, onModeChange() {}, onQuestionChange() {}, onSearch() {}, onSelect() {}, onNewSearch() {}, onLogout() {}, accountPanel: panel };

test('only administrators see management navigation; ordinary users cannot render account data', () => {
  assert.ok(!render(WorkspaceShell, workspace).includes('用户管理'));
  assert.ok(render(WorkspaceShell, { ...workspace, role: 'admin' }).includes('用户管理'));
  const denied = render(WorkspaceShell, { ...workspace, view: 'accounts' });
  assert.ok(!denied.includes('name&lt;script&gt;'));
  const allowed = render(WorkspaceShell, { ...workspace, role: 'admin', view: 'accounts' });
  assert.match(allowed, /name&lt;script&gt;&amp;/);
  assert.match(allowed, /aria-current="page"/);
});

test('account cards escape identifiers, expose server status and accessible pagination without secrets', () => {
  const markup = render(AccountsPanel, panel);
  for (const label of ['当前账号', '已启用', '管理员', '已完成首改', '停用账号', '重置密码', '撤销全部会话', '账号分页']) assert.ok(markup.includes(label), label);
  assert.match(markup, /name&lt;script&gt;&amp;/);
  assert.match(markup, />上一页<\/button>/);
  assert.match(markup, /disabled="">上一页/);
  assert.ok(!markup.includes('password_hash'));
  const disabled = render(AccountsPanel, { ...panel, accounts: { items: [{ ...account, active: false, must_change_password: true }], next_offset: null }, offset: 10 });
  assert.match(disabled, /已停用/); assert.match(disabled, /下次登录需改密/); assert.match(disabled, /启用账号/); assert.match(disabled, /第 2 页/);
});

test('every mutation requires explicit confirmation and accurately describes its consequences', () => {
  for (const action of ['create', 'enable', 'disable', 'reset', 'revoke']) {
    const intent = { action, target: action === 'create' ? null : account };
    const markup = render(AccountActionDialog, { intent, userId: account.user_id, error: '', busy: false, onClose() {}, onSubmit() {} });
    const confirmation = markup.match(/<input[^>]*name="confirmed"[^>]*>/)?.[0];
    assert.ok(confirmation); assert.match(confirmation, /required=""/);
    assert.match(markup, /aria-describedby="account-dialog-impact"/);
    assert.ok(markup.includes(accountImpact(intent, account.user_id)));
    assert.equal((markup.match(/type="password"/g) || []).length, ['create', 'reset'].includes(action) ? 2 : 0);
    assert.ok(!/type="password"[^>]*value=/.test(markup));
    if (action === 'create') assert.match(markup, /value="user" selected=""/);
  }
  const busy = render(AccountActionDialog, { intent: { action: 'revoke', target: account }, userId: account.user_id, error: '', busy: true, onClose() {}, onSubmit() {} });
  assert.match(busy, /type="submit"[^>]*disabled=""/);
  assert.match(busy, /已发送的操作可能仍会完成/);
});

test('public failure messages never echo arbitrary server data or credential strings', () => {
  const secret = 'private-password-token-hash';
  assert.match(accountFailure({ status: 409, body: { detail: 'LAST_ACTIVE_ADMIN' } }), /最后一个/);
  assert.match(accountFailure({ status: 409, body: { detail: 'USERNAME_EXISTS' } }), /已存在/);
  for (const status of [401, 403, 404, 409, 422, 500, 503]) assert.ok(!accountFailure({ status, body: { detail: secret } }).includes(secret));
  assert.match(accountFailure(null), /不要直接重复提交/);
});
