const {test}=require('node:test');
const assert=require('node:assert/strict');
const {harness}=require('./history-hook-harness.cjs');
const create=options=>harness('lib/use-recorded-search.ts','useRecordedSearch',options);
function success(body,replayed=false){return{replayed,history:{entry:{history_id:'saved'},q:body.q,k:body.k,search_mode:body.document_id?'document':'library',document_id:body.document_id,target_available:body.document_id?true:null}};}

test('new explicit submissions use POST once synchronously and allocate different IDs even for identical questions',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit(' question ',5);h.value.submit('question',5);assert.equal(h.calls.length,1);assert.equal(h.calls[0].method,'searchAndRecordHistory');const first=h.calls[0].args[0];h.calls[0].resolve(success(first));await p;await h.settle();assert.equal(h.results.length,1);assert.equal(h.value.pending,false);
 const p2=h.value.submit('question',5);assert.notEqual(h.calls[1].args[0].request_id,first.request_id);h.calls[1].resolve(success(h.calls[1].args[0]));await p2;
});
test('unknown submission blocks new IDs and verification sends exact same captured input once',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit('original',3,'doc');const body=h.calls[0].args[0];h.calls[0].reject(new h.ApiError(503));await p;await h.settle();assert.equal(h.value.pending,true);await h.value.submit('changed',10);assert.equal(h.calls.length,1);
 const verify=h.value.verify();assert.equal(JSON.stringify(h.calls[1].args[0]),JSON.stringify(body));h.calls[1].resolve(success(body,true));await verify;await h.settle();assert.equal(h.results[0].replayed,true);assert.equal(h.value.pending,false);
});
test('pending409 retains request while failed/interrupted/limit/deleted errors need an explicit new submit',async t=>{
 for(const [status,code,pending] of [[409,'HISTORY_REQUEST_PENDING',true],[409,'HISTORY_REQUEST_FAILED',false],[409,'HISTORY_REQUEST_INTERRUPTED',false],[409,'HISTORY_LIMIT_REACHED',false],[410,'HISTORY_DELETED',false]]){
 const h=create();t.after(()=>h.close());const p=h.value.submit('q',3);h.calls[0].reject(new h.ApiError(status,code));await p;await h.settle();assert.equal(h.value.pending,pending,code);assert.equal(h.calls.length,1);assert.equal(h.results.length,0);}
});
test('leaving search cancels wait and refuses late success but preserves same-ID verification',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit('q',3);const first=h.calls[0];h.value.cancel();first.resolve(success(first.args[0]));await p;await h.settle();assert.equal(h.results.length,0);assert.equal(h.value.pending,true);assert.equal(first.cancelled,1);const verify=h.value.verify();h.calls[1].resolve(success(first.args[0],true));await verify;assert.equal(h.results.length,1);
});
test('switching account clears pending input and a late response cannot cross identities',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit('private A question',3);const old=h.calls[0];h.update({userId:'B'});old.resolve(success(old.args[0]));await p;await h.settle();assert.equal(h.results.length,0);assert.equal(h.value.pending,false);await h.value.verify();assert.equal(h.calls.length,1);assert.equal(h.value.notice,'');
});
test('recorded search401/403 reset request before session handling',async t=>{
 for(const status of [401,403]){const h=create();t.after(()=>h.close());const p=h.value.submit('q',3);h.calls[0].reject(new h.ApiError(status));await p;await h.settle();assert.equal(h.sessions.length,1);assert.equal(h.value.pending,false);assert.equal(h.results.length,0);}
});
test('changed response conditions are refused and require explicit same-ID verification',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit('original',5);const response=success(h.calls[0].args[0]);response.history.q='other';h.calls[0].resolve(response);await p;await h.settle();assert.equal(h.results.length,0);assert.equal(h.value.pending,true);
});
test('ending unknown verification does not submit or claim server cancellation',async t=>{
 const h=create();t.after(()=>h.close());const p=h.value.submit('q',3);h.calls[0].reject(new Error('offline'));await p;h.value.dismiss();await h.settle();assert.equal(h.calls.length,1);assert.equal(h.value.pending,false);assert.match(h.value.notice,/服务器可能已保存/);
});
