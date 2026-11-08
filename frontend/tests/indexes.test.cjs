const {test}=require('node:test');
const assert=require('node:assert/strict');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const {loadTs}=require('./load-workspace.cjs');
const {harness}=require('./audit-hook-harness.cjs');
const {IndexesPanel}=loadTs('components/workspace/indexes.tsx');
const {WorkspaceShell}=loadTs('components/workspace/workspace.tsx');
const data=()=>({active_index_id:'active',index_epoch:3,profiles:[{profile_id:'p',name:'colpali_full_v1',status:'validated',config_sha256:'<script>',identity_matches:true,encoder_sha256:'sha'}],indexes:[{index_id:'active',status:'ready',page_count:13,vector_count:13403},{index_id:'old',status:'ready',page_count:13,vector_count:13403}],operations:[],next_offset:null,next_operation_offset:null});
const create=initial=>harness('lib/use-indexes.ts','useIndexes',{csrfToken:'csrf',onChanged(){},...initial});
const event=confirmed=>({preventDefault(){},currentTarget:{data:{confirmed}}});
async function loaded(h){h.panel;h.calls[0].resolve(data());await h.settle();}
test('index view cancels late list across account and disabled view',async t=>{
 const h=create();t.after(()=>h.close());h.panel;const old=h.calls[0];h.update({userId:'other'});old.resolve(data());await h.settle();assert.equal(h.panel.response,null);assert.equal(old.cancelled,1);
 const late=h.calls.at(-1);h.update({enabled:false});late.resolve(data());await h.settle();assert.equal(h.panel.response,null);assert.equal(late.cancelled,1);
});
test('index confirmation carries exact target epoch and blocks duplicate submit',async t=>{
 let changes=0;const h=create({onChanged(){changes++;}});t.after(()=>h.close());await loaded(h);
 h.panel.onOpen('activate',data().indexes[1]);await h.panel.onSubmit(event(null));assert.equal(h.calls.length,1);
 const work=h.panel.onSubmit(event('yes'));const again=h.panel.onSubmit(event('yes'));await again;
 assert.equal(h.calls.length,2);assert.equal(h.calls[1].method,'activateIndex');const body=h.calls[1].args[0];assert.equal(body.index_id,'old');assert.equal(body.active_index_id,'active');assert.equal(body.index_epoch,3);assert.equal(body.confirmed,true);
 h.calls[1].resolve({status:'completed'});await work;await h.settle();assert.equal(changes,1);assert.equal(h.panel.intent,null);assert.equal(h.calls[2].method,'getIndexManagement');
});
test('unknown write clears captured state and refreshes only without automatic retry',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onOpen('rebuild',data().indexes[0]);const work=h.panel.onSubmit(event('yes'));h.calls[1].reject(new h.ApiError(503,'private-secret'));await work;await h.settle();
 assert.match(h.panel.notice,/尚未确认/);assert.ok(!h.panel.notice.includes('private-secret'));assert.equal(h.panel.intent,null);assert.deepEqual(h.calls.map(c=>c.method),['getIndexManagement','rebuildIndex','getIndexManagement']);
});
test('late mutation after leaving cannot announce success or invalidate another account',async t=>{
 let changes=0;const h=create({onChanged(){changes++;}});t.after(()=>h.close());await loaded(h);h.panel.onOpen('activate',data().indexes[1]);const work=h.panel.onSubmit(event('yes'));h.update({enabled:false,userId:'B'});h.calls[1].resolve({status:'completed'});await work;await h.settle();assert.equal(changes,0);assert.equal(h.panel.notice,'');assert.equal(h.panel.response,null);
});
test('permission errors clear management state before session callback',async t=>{
 for(const status of [401,403]){const h=create();t.after(()=>h.close());await loaded(h);h.panel.onOpen('verify',data().indexes[0]);const work=h.panel.onSubmit(event('yes'));h.calls[1].reject(new h.ApiError(status));await work;await h.settle();assert.equal(h.sessions.length,1);assert.equal(h.panel.response,null);assert.equal(h.panel.intent,null);}
});
test('independent page cursors clear stale intent and list failure clears rows',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onOpen('verify',data().indexes[0]);h.panel.onPage(10,true);h.panel;assert.equal(h.panel.intent,null);assert.equal(h.calls[1].args[0],0);assert.equal(h.calls[1].args[1],10);
 h.calls[1].reject(new h.ApiError(503));await h.settle();assert.equal(h.panel.response,null);assert.match(h.panel.error,/无法确认/);
});
test('index panel explains full-vector costs and has admin-only single-main workspace',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);const html=renderToStaticMarkup(React.createElement(IndexesPanel,h.panel));
 assert.match(html,/1031 × 128/);assert.match(html,/不重新编码页面/);assert.match(html,/排除文件封装/);assert.match(html,/&lt;script&gt;/);assert.ok(!html.includes('<script>'));
 const props={username:'admin',role:'admin',view:'indexes',indexPanel:h.panel,question:'',notice:'',searchMode:'library'};
 const shell=renderToStaticMarkup(React.createElement(WorkspaceShell,props));assert.equal((shell.match(/<main/g)||[]).length,1);assert.match(shell,/id="indexes-heading"/);
 const denied=renderToStaticMarkup(React.createElement(WorkspaceShell,{...props,role:'user'}));assert.match(denied,/无配置管理权限/);assert.ok(!denied.includes('id="indexes-heading"'));assert.ok(!denied.includes('title="配置身份与回退"'));
});
test('running operation blocks new actions and unsafe generations cannot activate',async t=>{
 const h=create();t.after(()=>h.close());h.panel;const d=data();d.operations=[{operation_id:'op',kind:'rebuild',status:'running',source_id:'active',target_id:'new',metrics:{}}];d.indexes[1].status='failed';h.calls[0].resolve(d);await h.settle();
 const html=renderToStaticMarkup(React.createElement(IndexesPanel,h.panel));assert.match(html,/disabled="">重建候选/);assert.match(html,/disabled="">激活 \/ 回退/);assert.match(html,/待完成/);
});
