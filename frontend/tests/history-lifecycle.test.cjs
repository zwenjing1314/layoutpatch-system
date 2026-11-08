const {test}=require('node:test');
const assert=require('node:assert/strict');
const {harness}=require('./history-hook-harness.cjs');
const create=options=>harness('lib/use-history.ts','useHistory',options);
const entry={history_id:'history-a',title:'原标题',original_title:'原标题',version:1,pinned_at:null,hit_count:2,created_at:'2026-11-08T08:00:00Z'};
const event=data=>({preventDefault(){},currentTarget:{data}});
async function loaded(h,next_offset=null){h.panel;h.calls[0].resolve({items:[entry],next_offset,scope_version:'s1'});await h.settle();}

test('history list cancellation prevents private A titles reaching B or disabled workspace',async t=>{
 const h=create({enabled:false});t.after(()=>h.close());h.panel;assert.equal(h.calls.length,0);h.update({enabled:true});const old=h.calls[0];h.update({userId:'B'});old.resolve({items:[entry],scope_version:'s1'});await h.settle();assert.equal(h.panel.response,null);assert.equal(old.cancelled,1);
 h.update({enabled:false});h.calls[1].resolve({items:[entry],scope_version:'s1'});await h.settle();assert.equal(h.panel.response,null);
});
test('history pagination uses10 and restarts when snapshot changed across pages',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h,10);h.panel.onNext();assert.equal(h.panel.offset,10);assert.deepEqual(h.calls[1].args,[10,10]);h.calls[1].resolve({items:[entry],scope_version:'new',next_offset:null});await h.settle();assert.equal(h.panel.offset,0);assert.deepEqual(h.calls[2].args,[10,0]);assert.equal(h.panel.response,null);
});
test('opening history only GETs detail and a late previous detail never restores old results',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onOpen(entry);const a=h.calls[1];h.panel.onOpen({...entry,history_id:'b'});const b=h.calls[2];a.resolve({entry});b.resolve({entry:{...entry,history_id:'b'},q:'saved'});await h.settle();assert.equal(a.cancelled,1);assert.equal(h.opened.length,1);assert.equal(h.opened[0].entry.history_id,'b');assert.deepEqual(h.calls.map(c=>c.method),['listQueryHistory','getQueryHistory','getQueryHistory']);
 h.panel.onOpen(entry);const late=h.calls[3];h.value.cancelOpen();late.resolve({entry});await h.settle();assert.equal(h.opened.length,1);
});
test('history rename validates one line and sends original version once with no optimistic mutation',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onMenu(entry,'rename');h.panel.onSubmit(event({title:'\n'}));assert.equal(h.calls.length,1);assert.match(h.panel.error,/1—100/);
 h.panel.onSubmit(event({title:'新标题'}));h.panel.onSubmit(event({title:'重复'}));assert.equal(h.calls.length,2);assert.equal(JSON.stringify(h.calls[1].args),JSON.stringify(['history-a',{version:1,title:'新标题'}]));assert.equal(h.updated.length,0);
 h.calls[1].resolve({...entry,title:'新标题',version:2});await h.settle();assert.equal(h.updated.length,1);assert.equal(h.panel.intent,null);assert.match(h.panel.notice,/原问题保持/);
});
test('pin failure and stale rename never automatically repeat a write',async t=>{
 for(const status of [409,503]){const h=create();t.after(()=>h.close());await loaded(h);h.panel.onMenu(entry,'pin');assert.equal(JSON.stringify(h.calls[1].args),JSON.stringify(['history-a',{version:1,pinned:true}]));h.calls[1].reject(new h.ApiError(status,'private detail'));await h.settle();assert.equal(h.updated.length,0);assert.equal(h.calls.filter(c=>c.method==='updateQueryHistory').length,1);assert.ok(!h.panel.notice.includes('private detail'));assert.match(h.panel.notice,status===409?/版本已变化/:/尚未确认/);}
});
test('history delete requires explicit confirmation and clears selected reference on success or unknown outcome',async t=>{
 for(const success of [true,false]){const h=create();t.after(()=>h.close());await loaded(h);h.panel.onMenu(entry,'delete');h.panel.onSubmit(event({}));assert.equal(h.calls.length,1);h.panel.onSubmit(event({confirmed:'yes'}));assert.equal(JSON.stringify(h.calls[1].args),JSON.stringify(['history-a',{version:1,confirmed:true}]));if(success)h.calls[1].resolve({deleted:true});else h.calls[1].reject(new h.ApiError(503));await h.settle();assert.deepEqual(h.unavailable,['history-a']);assert.equal(h.calls.filter(c=>c.method==='deleteQueryHistory').length,1);}
});
test('history write response cannot repopulate after identity changed',async t=>{
 const h=create();t.after(()=>h.close());await loaded(h);h.panel.onMenu(entry,'pin');const write=h.calls[1];h.update({userId:'B'});write.resolve({...entry,pinned_at:'now',version:2});await h.settle();assert.equal(write.cancelled,1);assert.equal(h.updated.length,0);assert.equal(h.panel.notice,'');
});
test('history401 and403 erase private state before identity error handler',async t=>{
 for(const status of [401,403]){const h=create();t.after(()=>h.close());await loaded(h);h.panel.onOpen(entry);h.calls[1].reject(new h.ApiError(status));await h.settle();assert.equal(h.sessions.length,1);assert.equal(h.panel.response,null);assert.equal(h.panel.opening,null);}
});
