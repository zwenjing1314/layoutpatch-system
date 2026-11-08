const {test}=require('node:test');
const assert=require('node:assert/strict');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const {loadTs}=require('./load-workspace.cjs');
const {harness}=require('./audit-hook-harness.cjs');
const {AuditPanel}=loadTs('components/workspace/audit.tsx');
const {WorkspaceShell}=loadTs('components/workspace/workspace.tsx');
const create=options=>harness('lib/use-audit.ts','useAudit',options);
const event=data=>({preventDefault(){},currentTarget:{data}});
const data=(scope='one',next_offset=10)=>({items:[{event_id:'safe-id',category:'history',action:'create',actor_id:'<script>&',actor_type:'user',target_id:'id',code:'OK',outcome:'success',occurred_at:1}],scope_version:scope,next_offset});
async function loaded(h){h.panel;h.calls[0].resolve(data());await h.settle();}

test('audit cancels late responses across disabled view and identity change',async t=>{
 const h=create({enabled:false});t.after(()=>h.close());h.panel;assert.equal(h.calls.length,0);
 h.update({enabled:true});const old=h.calls[0];h.update({userId:'B'});old.resolve(data());await h.settle();assert.equal(h.panel.response,null);assert.equal(old.cancelled,1);
 const late=h.calls.at(-1);h.update({enabled:false});late.resolve(data());await h.settle();assert.equal(h.panel.response,null);assert.equal(late.cancelled,1);
});
test('audit fixed-window pagination restarts at first page when scope changes',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);const window=h.calls[0].args.slice(0,2);h.panel.onNext();h.panel;
 assert.equal(h.calls[1].args[3],10);assert.deepEqual(h.calls[1].args.slice(0,2),window);
 h.calls[1].resolve(data('changed',null));await h.settle();assert.equal(h.panel.offset,0);assert.equal(h.calls[2].args[3],0);assert.match(h.panel.notice,/返回第一页/);
});
test('audit filters validate before request and task switch never calls a mutation',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onSubmit(event({start:'2026-01-01',end:'2026-02-01'}));h.panel;assert.equal(h.calls.length,1);assert.match(h.panel.error,/31天/);
 h.panel.onSubmit(event({start:'2026-01-01',end:'2026-01-31',source:'history',state:'success',actor:'00000000-0000-4000-8000-000000000001'}));h.panel;
 assert.equal(h.calls[1].args[4],'history');assert.equal(h.calls[1].args[7],'success');assert.equal(h.calls[1].args[1]-h.calls[1].args[0],31*86400);
 h.panel.onTab('tasks');h.panel;assert.equal(h.calls.at(-1).method,'listAuditTasks');assert.equal(h.panel.response,null);assert.equal(h.panel.offset,0);
 assert.ok(h.calls.every(c=>/^listAudit/.test(c.method)));
});
test('audit permission errors erase state before notifying session handler',async t=>{
 for(const status of [401,403]){const h=create();t.after(()=>h.close());await loaded(h);h.panel.onRefresh();h.panel;h.calls.at(-1).reject(new h.ApiError(status));await h.settle();assert.equal(h.sessions.length,1);assert.equal(h.panel.response,null);}
});
test('audit unavailable and changed snapshots expose safe feedback without automatic retry',async t=>{
 for(const status of [409,422,503]){const h=create();t.after(()=>h.close());h.panel;h.calls[0].reject(new h.ApiError(status,'private-path-secret'));await h.settle();assert.equal(h.panel.response,null);assert.ok(h.panel.error);assert.ok(!h.panel.error.includes('private-path'));assert.equal(h.calls.length,1);}
});
test('audit panel is readonly, escaped and explicit about retention and current tasks',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);const html=renderToStaticMarkup(React.createElement(AuditPanel,h.panel));
 assert.match(html,/&lt;script&gt;&amp;/);assert.ok(!html.includes('<script>'));assert.match(html,/不自动过期/);assert.match(html,/物理清理可移除关联任务/);assert.match(html,/每页10条/);assert.ok(!html.includes('<a '));assert.ok(!html.includes('type="password"'));
 h.panel.onTab('tasks');h.panel;h.calls.at(-1).resolve({items:[],scope_version:'tasks'});await h.settle();const empty=renderToStaticMarkup(React.createElement(AuditPanel,h.panel));assert.match(empty,/仅显示当前任务状态/);assert.match(empty,/没有匹配记录/);
});
test('workspace audit entry is admin-only and mounts one main',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);
 const props={username:'A',role:'admin',view:'audit',auditPanel:h.panel,question:'',notice:'',searchMode:'library'};
 const html=renderToStaticMarkup(React.createElement(WorkspaceShell,props));assert.equal((html.match(/<main/g)||[]).length,1);assert.equal((html.match(/id="audit-heading"/g)||[]).length,1);
 const denied=renderToStaticMarkup(React.createElement(WorkspaceShell,{...props,role:'user'}));assert.match(denied,/无审计查询权限/);assert.ok(!denied.includes('id="audit-heading"'));assert.ok(!denied.includes('title="审计与任务"'));
});
