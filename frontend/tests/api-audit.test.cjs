const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
test('audit generated SDK sends two readonly admin GETs with explicit windows and filters',()=>{
 const calls=[],context={exports:{},require:p=>p.endsWith('/request')?{request:(_,o)=>{calls.push(o);return o;}}:{OpenAPI:{}}};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/api/generated/services/AuditService.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,context);
 const api=context.exports.AuditService;api.listAuditEvents(1,2,10,20,'account','actor','target','success');api.listAuditTasks(1,2,10,20,'search','failed','owner','doc');
 assert.deepEqual(calls.map(c=>c.url),['/admin/events','/admin/tasks']);assert.ok(calls.every(c=>c.method==='GET'&&c.body===undefined));
 assert.equal(JSON.stringify(calls[0].query),JSON.stringify({since:1,until:2,limit:10,offset:20,category:'account',actor_id:'actor',target_id:'target',outcome:'success'}));
 assert.equal(JSON.stringify(calls[1].query),JSON.stringify({since:1,until:2,limit:10,offset:20,kind:'search',status:'failed',owner_id:'owner',document_id:'doc'}));
});
