const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { SharingPanel, SharingDialog } = loadTs('components/workspace/sharing.tsx');
const { WorkspaceShell } = loadTs('components/workspace/workspace.tsx');
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const doc = { document_id: 'own-doc', display_name: 'report<script>&', version: 1, page_count: 12, visibility: 'private', access_version: 1, can_publish: true };
const panel = { response: { items: [doc], next_offset: 10 }, offset: 0, busy: false, actionBusy: false, notice: '', error: '', intent: null, onRefresh() {}, onPrevious() {}, onNext() {}, onOpen() {}, onClose() {}, onSubmit() {} };
const workspace = { username: 'A', role: 'user', question: '', submittedQuestion: '', busy: false, notice: '', result: null, selected: null, image: null, imageBusy: false, imageError: '', searchMode: 'library', targetDocument: null, onModeChange() {}, onQuestionChange() {}, onSearch() {}, onSelect() {}, onNewSearch() {}, onLogout() {}, sharingPanel: panel };

test('sharing navigation and management content are administrator-only', () => {
  assert.ok(!render(WorkspaceShell, workspace).includes('共享管理'));
  assert.ok(render(WorkspaceShell, { ...workspace, role: 'admin' }).includes('共享管理'));
  const denied = render(WorkspaceShell, { ...workspace, view: 'sharing' });
  assert.match(denied, /无共享管理权限/); assert.ok(!denied.includes('report&lt;script&gt;'));
  assert.match(render(WorkspaceShell, { ...workspace, role: 'admin', view: 'sharing' }), /report&lt;script&gt;&amp;/);
});

test('sharing cards show own scope, current epoch and readiness without deletion controls', () => {
  const markup = render(SharingPanel, panel);
  for (const text of ['当前管理员本人上传', '授权版本 1', '仅本人', '发布共享', '共享管理分页', '每页10份']) assert.ok(markup.includes(text), text);
  assert.match(markup, /report&lt;script&gt;&amp;/); assert.match(markup, /disabled="">上一页/);
  assert.ok(!markup.includes('删除'));
  const unready = render(SharingPanel, { ...panel, response: { items: [{ ...doc, can_publish: false }], next_offset: null } });
  assert.match(unready, /disabled="">发布共享/);
  const shared = render(SharingPanel, { ...panel, response: { items: [{ ...doc, visibility: 'shared', can_publish: false }], next_offset: null } });
  assert.match(shared, />撤回共享<\/button>/); assert.ok(!/disabled="">撤回共享/.test(shared));
});

test('both sharing dialogs require confirmation and disclose scope, old links and retained bytes', () => {
  for (const visibility of ['private', 'shared']) {
    const markup = render(SharingDialog, { doc: { ...doc, visibility }, busy: false, error: '', onClose() {}, onSubmit() {} });
    assert.match(markup.match(/<input[^>]*name="confirmed"[^>]*>/)[0], /required=""/);
    assert.match(markup, /aria-describedby="sharing-impact"/); assert.match(markup, /授权版本 1/);
    assert.match(markup, /不会复活旧图片和裁剪链接/); assert.match(markup, /不会删除文档或重新编码/);
    if (visibility === 'shared') assert.match(markup, /无法远程收回/);
    else assert.match(markup, /所有已登录且完成首改/);
    assert.ok(markup.indexOf('>取消</button>') < markup.indexOf('type="submit"'));
  }
  const busy = render(SharingDialog, { doc, busy: true, error: '', onClose() {}, onSubmit() {} });
  assert.match(busy, /type="submit"[^>]*disabled=""/); assert.match(busy, /停止等待不表示服务器已取消/);
});

test('empty management scope points to own upload and exposes no fabricated documents', () => {
  const markup = render(SharingPanel, { ...panel, response: { items: [], next_offset: null } });
  assert.match(markup, /暂无本人可管理文档/); assert.match(markup, /上传与任务/); assert.ok(!markup.includes('ws-sharing-card'));
});
