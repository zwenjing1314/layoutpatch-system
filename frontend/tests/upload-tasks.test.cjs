const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { taskStatus, taskError, boundedTaskRequest } = loadTs('lib/task-state.ts');
const { RequestGeneration } = loadTs('lib/workspace-lifecycle.ts');
const { UploadTasksPanel } = loadTs('components/workspace/upload-tasks.tsx');
const { WorkspaceShell } = loadTs('components/workspace/workspace.tsx');
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const job = { job_id: '11111111-1111-1111-1111-111111111111', document_id: 'doc-a', display_name: '私有 <script>alert(1)</script>.pdf', page_count: 4, status: 'failed', stage: 'encoding', progress: 40, attempt: 1, error_code: 'PAGE_ENCODING_FAILED', retry_available: true, cancel_available: false, cancel_requested_at: null, updated_at: '2026-11-08T01:00:00Z', attempts: [{ attempt: 1, status: 'failed', stage: 'encoding', progress: 40, error_code: 'PAGE_ENCODING_FAILED', cancel_requested_at: null, created_at: '2026-11-08T01:00:00Z', ended_at: '2026-11-08T01:00:10Z' }] };
const panel = { filename: '', inputKey: 0, uploadBusy: false, uploadError: '', uploadUncertain: false, jobs: { items: [job], next_cursor: null }, listBusy: false, listError: '', paused: false, page: 1, actionBusy: null, actionError: '', onFile() {}, onUpload() {}, onStopUpload() {}, onRefresh() {}, onPrevious() {}, onNext() {}, onAction() {}, onBrowse() {} };

test('running cancellation is pending and never described as already cancelled', () => {
  assert.equal(taskStatus({ ...job, status: 'running', cancel_requested_at: 'saved' }), '等待取消检查点');
  assert.equal(taskStatus({ ...job, status: 'cancelled' }), '已取消');
  assert.match(taskError('PAGE_ENCODING_FAILED'), /编码失败/);
  assert.ok(!taskError('UNEXPECTED_CODE').includes('UNEXPECTED_CODE'));
});
test('task view escapes filenames and shows durable attempts with server action flags', () => {
  const markup = render(UploadTasksPanel, panel);
  assert.ok(markup.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.ok(!markup.includes('<script>'));
  for (const text of ['第 1 次尝试', '尝试记录（1）', 'PAGE_ENCODING_FAILED', '重试此任务']) assert.ok(markup.includes(text));
  assert.ok(!markup.includes('取消任务'));
  const waiting = render(UploadTasksPanel, { ...panel, jobs: { items: [{ ...job, status: 'running', retry_available: false, cancel_requested_at: 'saved', error_code: null }], next_cursor: null } });
  assert.match(waiting, /当前操作结束前不会显示为已取消/);
  assert.ok(!waiting.includes('重试此任务'));
});
test('ambiguous upload offers same identifier resend and stop-waiting is separate from task cancel', () => {
  const uncertain = render(UploadTasksPanel, { ...panel, filename: 'doc.pdf', uploadUncertain: true });
  assert.match(uncertain, /同标识重试发送/);
  const uploading = render(UploadTasksPanel, { ...panel, filename: 'doc.pdf', uploadBusy: true });
  assert.match(uploading, /停止等待发送/);
  assert.match(uploading, /type="submit" disabled=""/);
  assert.ok(!uploading.includes('取消任务'));
});
test('completed task links to authorized selection and unavailable retry gives explicit reupload guidance', () => {
  const complete = render(UploadTasksPanel, { ...panel, jobs: { items: [{ ...job, status: 'completed', progress: 100, retry_available: false, error_code: null }], next_cursor: null } });
  assert.match(complete, /到文档列表选择检索/);
  assert.ok(!complete.includes('重试此任务'));
  const unavailable = render(UploadTasksPanel, { ...panel, jobs: { items: [{ ...job, retry_available: false }], next_cursor: null } });
  assert.match(unavailable, /重新选择源PDF上传/);
});
test('task shell hides search composer and original image while retaining logout navigation', () => {
  const markup = render(WorkspaceShell, { view: 'tasks', taskPanel: panel, username: 'isolated', role: 'user', searchMode: 'library', notice: '' });
  for (const text of ['上传PDF', '本人持久任务', '退出 / 换号']) assert.ok(markup.includes(text));
  assert.ok(!markup.includes('name="q"'));
  assert.ok(!markup.includes('<img'));
  assert.ok(!markup.includes('检索历史'));
});
test('bounded task wait rejects even if abort loses the race and removes its registration', async () => {
  let cancelled = 0, registered;
  const request = new Promise(() => {}); request.cancel = () => cancelled++;
  const generation = { track(fn) { registered = fn; return () => { registered = undefined; }; } };
  await assert.rejects(boundedTaskRequest(request, generation, 10), /TASK_REQUEST_TIMEOUT/);
  assert.equal(cancelled, 1); assert.equal(registered, undefined);
});
test('identity reset rejects late task responses without cancelling content queries', async () => {
  const tasks = new RequestGeneration(), content = new RequestGeneration();
  const contentStamp = content.current(), stamp = tasks.current();
  let finish, cancelled = 0;
  const request = new Promise(resolve => { finish = resolve; }); request.cancel = () => cancelled++;
  const waiting = boundedTaskRequest(request, tasks, 1000);
  tasks.reset(); finish('old private task');
  await assert.rejects(waiting, /TASK_REQUEST_CANCELLED/);
  assert.equal(tasks.accepts(stamp), false); assert.equal(cancelled, 1);
  assert.equal(content.accepts(contentStamp), true);
});
