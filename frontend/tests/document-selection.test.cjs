const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { searchDocumentId, matchesSearchTarget, documentStatus, unavailableReason } = loadTs('lib/document-selection.ts');
const { RequestGeneration } = loadTs('lib/workspace-lifecycle.ts');
const { DocumentPicker, ScopeSwitch } = loadTs('components/workspace/document-picker.tsx');
const { QueryComposer, WorkspaceShell } = loadTs('components/workspace/workspace.tsx');
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const doc = { document_id: '11111111-1111-1111-1111-111111111111', document_version_id: 'version-a', display_name: '同名 <script>.pdf', page_count: 5, access: 'own', searchable: true, status: 'ready', job_status: null, unsearchable_reason: null, created_at: '2026-11-08T00:00:00+08:00' };
const basePicker = { name: '', response: { items: [], next_cursor: null, scope_version: 'one' }, busy: false, error: '', selected: null, page: 1, onNameChange() {}, onSelect() {}, onPrevious() {}, onNext() {}, onRefresh() {} };

test('document scope never falls back to the library for missing or unready selection', () => {
  assert.equal(searchDocumentId('library', doc), undefined);
  assert.equal(searchDocumentId('document', doc), doc.document_id);
  for (const selection of [null, { ...doc, searchable: false }, { ...doc, document_version_id: null }]) assert.throws(() => searchDocumentId('document', selection));
});
test('search response must match submitted mode, document and every page version', () => {
  const response = { search_mode: 'document', document_id: doc.document_id, items: [{ document_id: doc.document_id, document_version_id: doc.document_version_id }] };
  assert.equal(matchesSearchTarget(response, 'document', doc), true);
  assert.equal(matchesSearchTarget(response, 'library', null), false);
  assert.equal(matchesSearchTarget({ ...response, document_id: 'other' }, 'document', doc), false);
  for (const hit of [{ document_id: 'other', document_version_id: 'version-a' }, { document_id: doc.document_id, document_version_id: 'old' }]) assert.equal(matchesSearchTarget({ ...response, items: [hit] }, 'document', doc), false);
  assert.equal(matchesSearchTarget({ search_mode: 'library', document_id: null, items: [] }, 'library', null), true);
});
test('filter cancellation is independent of content search; session lock cancels both', () => {
  const list = new RequestGeneration(), search = new RequestGeneration();
  const searchStamp = search.current(); let cancelled = 0;
  const listStamp = list.current(); list.track(() => cancelled++); list.reset();
  assert.equal(list.accepts(listStamp), false); assert.equal(search.accepts(searchStamp), true); assert.equal(cancelled, 1);
  const currentList = list.current(); list.reset(); search.reset();
  assert.equal(list.accepts(currentList), false); assert.equal(search.accepts(searchStamp), false);
});
test('late page response cannot replace a later filename filter even when abort loses the race', async () => {
  const generation = new RequestGeneration(), shown = [];
  let finish;
  const stamp = generation.current(), pending = new Promise(resolve => { finish = resolve; });
  const update = pending.then(value => { if (generation.accepts(stamp)) shown.push(value); });
  generation.reset(); finish('old filename page'); await update;
  assert.deepEqual(shown, []);
});
test('duplicate names stay distinguishable by stable radio IDs and readiness controls', () => {
  const unavailable = { ...doc, document_id: '22222222-2222-2222-2222-222222222222', searchable: false, status: 'registered', job_status: 'queued', unsearchable_reason: 'DOCUMENT_NOT_READY' };
  const markup = render(DocumentPicker, { ...basePicker, response: { items: [doc, unavailable], next_cursor: 'opaque', scope_version: 'one' }, selected: doc });
  assert.ok(markup.includes(doc.document_id)); assert.ok(markup.includes(unavailable.document_id));
  assert.ok(markup.includes('&lt;script&gt;')); assert.ok(!markup.includes('<script>'));
  assert.match(markup, /checked=""/); assert.match(markup, /<input(?=[^>]*disabled="")(?=[^>]*value="22222222)[^>]*>/);
  assert.match(markup, /排队中/); assert.match(markup, /尚未完成入库/);
});
test('filename, content input, empty/loading/error and cursor boundaries are distinct', () => {
  assert.match(render(DocumentPicker, basePicker), /当前没有可见文档/);
  assert.match(render(DocumentPicker, { ...basePicker, name: '%_' }), /没有匹配的文件名/);
  assert.match(render(DocumentPicker, { ...basePicker, busy: true, response: null }), /正在加载授权文档/);
  const error = render(DocumentPicker, { ...basePicker, response: null, error: '请刷新列表' });
  assert.match(error, /role="alert"/); assert.match(error, /请刷新列表/);
  assert.match(render(DocumentPicker, basePicker), /disabled="">上一页/);
  assert.match(render(DocumentPicker, basePicker), /disabled="">下一页/);
  assert.match(render(DocumentPicker, { ...basePicker, page: 2 }), /第 2 页/);
});
test('single-document composer blocks absent/unready targets but allows authorized selection', () => {
  const props = { question: '内容问题', busy: false, searchMode: 'document', inputRef: { current: null }, onQuestionChange() {}, onSearch() {} };
  assert.match(render(QueryComposer, props), /type="submit" disabled=""/);
  assert.match(render(QueryComposer, { ...props, targetDocument: { ...doc, searchable: false } }), /type="submit" disabled=""/);
  const ready = render(QueryComposer, { ...props, targetDocument: doc });
  assert.ok(!ready.includes('disabled=""')); assert.match(ready, /仅检索/); assert.match(ready, /ID 11111111/);
});
test('selected scope remains visible even when a new filter hides its row', () => {
  const props = { username: 'test', role: 'user', question: '', submittedQuestion: '', busy: false, notice: '', result: null, selected: null, image: null, imageBusy: false, imageError: '', searchMode: 'document', targetDocument: doc, documentPicker: { ...basePicker, name: 'nonmatching', selected: doc }, onModeChange() {}, onQuestionChange() {}, onSearch() {}, onSelect() {}, onNewSearch() {}, onLogout() {} };
  const markup = render(WorkspaceShell, props);
  assert.match(markup, /当前文档/); assert.match(markup, /ID 11111111/); assert.match(markup, /没有匹配的文件名/);
  const modes = render(ScopeSwitch, { mode: 'document', onChange() {} });
  assert.match(modes, /aria-pressed="true">单文档检索/);
});
test('own processing and index readiness have explicit text independent of color', () => {
  assert.equal(documentStatus({ ...doc, searchable: false, job_status: 'failed' }), '处理失败');
  assert.equal(documentStatus({ ...doc, searchable: false, job_status: 'running' }), '处理中');
  assert.equal(unavailableReason({ ...doc, searchable: false, unsearchable_reason: 'INDEX_INCOMPLETE' }), '页面索引不完整');
  assert.equal(unavailableReason(doc), '');
});
