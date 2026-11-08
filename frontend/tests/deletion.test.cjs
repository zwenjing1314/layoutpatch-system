const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { DeletionPanel, DeletionDialog } = loadTs('components/workspace/deletion.tsx');
const { WorkspaceShell } = loadTs('components/workspace/workspace.tsx');
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const doc={document_id:'own-id',display_name:'own<script>&',document_version_id:'ver',access_version:1,status:'ready',cleanup_status:null,attempt:null};
const panel={response:{items:[doc],next_offset:null},offset:0,busy:false,actionBusy:false,notice:'',error:'',intent:null,onRefresh(){},onPrevious(){},onNext(){},onOpen(){},onClose(){},onSubmit(){}};

test('all signed-in roles have deletion navigation; own scope and escaped names are explicit',()=>{
 const shell={username:'A',role:'user',question:'',submittedQuestion:'',busy:false,notice:'',result:null,selected:null,image:null,imageBusy:false,imageError:'',searchMode:'library',targetDocument:null,onModeChange(){},onQuestionChange(){},onSearch(){},onSelect(){},onNewSearch(){},onLogout(){},view:'deletion',deletionPanel:panel};
 for(const role of ['user','admin']){const markup=render(WorkspaceShell,{...shell,role});assert.match(markup,/删除与清理/);assert.match(markup,/own&lt;script&gt;&amp;/);assert.match(markup,/不能跨用户删除/);assert.equal((markup.match(/id="deletion-heading"/g)||[]).length,1);assert.equal((markup.match(/<main/g)||[]).length,1);}
});
test('tombstone statuses are explicit and only failed cleanup offers retry',()=>{
 for(const cleanup_status of ['queued','running','failed','completed']){const markup=render(DeletionPanel,{...panel,response:{items:[{...doc,status:'deleted',cleanup_status,attempt:2}],next_offset:null}});assert.ok(!markup.includes('>删除文档</button>'));assert.equal(markup.includes('>重试残留清理</button>'),cleanup_status==='failed');assert.match(markup,cleanup_status==='failed'?/清理失败/:cleanup_status==='completed'?/清理完成/:/访问已撤销/);}
});
test('deletion and retry dialogs disclose irreversible effect and require confirmation',()=>{
 for(const retrying of [false,true]){const markup=render(DeletionDialog,{doc:retrying?{...doc,status:'deleted',cleanup_status:'failed',attempt:2}:doc,busy:false,error:'',onClose(){},onSubmit(){}});assert.match(markup.match(/<input[^>]*name="confirmed"[^>]*>/)[0],/required=""/);assert.match(markup,/清理失败仍不可读取/);assert.match(markup,/无法远程收回/);assert.ok(markup.indexOf('>取消</button>')<markup.indexOf('type="submit"'));if(!retrying)assert.match(markup,/删除无法撤销/);else assert.match(markup,/不会恢复文档/);}
 const busy=render(DeletionDialog,{doc,busy:true,error:'',onClose(){},onSubmit(){}});assert.match(busy,/type="submit"[^>]*disabled=""/);
});
test('generated deletion SDK carries exact owner document version and retry attempt',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript'),calls=[];
 const source=ts.transpileModule(fs.readFileSync('lib/api/generated/services/DeletionService.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
 const context={exports:{},require:name=>name.endsWith('/request')?{request:(_,options)=>{calls.push(options);return options;}}:{OpenAPI:{}}};vm.runInNewContext(source,context);
 const service=context.exports.DeletionService,body={document_version_id:'ver',access_version:1,confirmed:true},retry={attempt:2,confirmed:true};
 service.listDeletionDocuments(10,20);service.deleteOwnDocument('doc',body);service.getDocumentCleanup('doc');service.retryDocumentCleanup('doc',retry);
 assert.equal(JSON.stringify(calls[0].query),JSON.stringify({limit:10,offset:20}));assert.equal(calls[1].url,'/documents/{document_id}/delete');assert.equal(calls[2].url,'/documents/{document_id}/cleanup');assert.equal(calls[3].url,'/documents/{document_id}/cleanup/retry');assert.equal(calls[1].body,body);assert.equal(calls[3].body,retry);
 for(const i of [1,3]){assert.equal(calls[i].method,'POST');assert.equal(calls[i].path.document_id,'doc');assert.equal(calls[i].mediaType,'application/json');}
});
