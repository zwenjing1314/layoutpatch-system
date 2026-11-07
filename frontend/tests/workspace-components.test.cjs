const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compiled = ts.transpileModule(fs.readFileSync('components/workspace/workspace.tsx', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
});
const context = { exports: {}, require };
vm.runInNewContext(compiled.outputText, context);
const { RetrievalResults, EvidencePanel, QueryComposer, WorkspaceShell } = context.exports;
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const hit = { page_id: 'page-a', document_name: '研究 <script>alert(1)</script> & 全角.pdf', page_number: 7, page_rank: 2, page_score: 12.345, width_px: 1200, height_px: 1600 };

test('result cards escape document names and retain actual page, rank, score and selection', () => {
  const markup = render(RetrievalResults, { result: { items: [hit] }, selected: hit, onSelect() {} });
  assert.ok(markup.includes('&lt;script&gt;alert(1)&lt;/script&gt; &amp; 全角.pdf'));
  assert.ok(!markup.includes('<script>'));
  assert.match(markup, /第 7 页 · 相关分数 12\.35/);
  assert.match(markup, /aria-pressed="true"/);
  assert.match(markup, />02</);
});
test('evidence empty, loading and failed states are explicit; only supplied Blob is rendered', () => {
  const common = { selected: hit, image: null, imageBusy: false, imageError: '', headingRef: { current: null }, onRetry() {} };
  assert.match(render(EvidencePanel, { ...common, selected: null }), /让证据回到眼前/);
  assert.match(render(EvidencePanel, { ...common, imageBusy: true }), /role="status"/);
  const failed = render(EvidencePanel, { ...common, imageError: '权限变化或加载失败' });
  assert.match(failed, /role="alert"/);
  assert.match(failed, /重试预览/);
  assert.ok(!failed.includes('<img'));
  const success = render(EvidencePanel, { ...common, image: 'blob:authorized-preview' });
  assert.match(success, /src="blob:authorized-preview"/);
  assert.match(success, /width="1200" height="1600"/);
  assert.ok(!success.includes('undefined'));
});
test('composer disallows blank or busy submissions and exposes the current library scope', () => {
  const common = { inputRef: { current: null }, onQuestionChange() {}, onSearch() {} };
  for (const props of [{ question: '   ', busy: false }, { question: '内容问题', busy: true }]) {
    assert.match(render(QueryComposer, { ...common, ...props }), /type="submit" disabled=""/);
  }
  const ready = render(QueryComposer, { ...common, question: '内容问题', busy: false });
  assert.ok(!ready.includes('disabled=""'));
  assert.match(ready, /个人与共享文档/);
  assert.match(ready, /name="k"/);
  assert.match(ready, /maxLength="2000"/i);
});
test('workspace exposes working navigation and view controls without future feature placeholders', () => {
  const props = { username: 'isolated-ui', role: 'user', question: '', submittedQuestion: '', busy: false, notice: '', result: null, selected: null, image: null, imageBusy: false, imageError: '', onQuestionChange() {}, onSearch() {}, onSelect() {}, onNewSearch() {}, onLogout() {} };
  const markup = render(WorkspaceShell, props);
  for (const label of ['工作台导航', '新检索', '退出 / 换号', '问题与结果', '页面预览']) assert.ok(markup.includes(label));
  for (const label of ['单文档检索', '上传与任务', '检索历史', '联网搜索']) assert.ok(!markup.includes(label));
  assert.match(markup, /aria-controls="workspace-navigation"/);
  const exiting = render(WorkspaceShell, { ...props, busy: true });
  assert.match(exiting, /正在退出登录/);
  assert.ok(!exiting.includes('正在查找相关页面'));
});
