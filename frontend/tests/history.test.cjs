const {test}=require('node:test');
const assert=require('node:assert/strict');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const {loadTs}=require('./load-workspace.cjs');
const {HistorySidebar,HistoryDialog,HistoryBanner}=loadTs('components/workspace/history.tsx');
const {QueryComposer,RetrievalResults,WorkspaceShell}=loadTs('components/workspace/workspace.tsx');
const {groupHistories,historyResult,canRepeatHistory,historyDate}=loadTs('lib/history-state.ts');
const render=(c,p)=>renderToStaticMarkup(React.createElement(c,p));
const entry={history_id:'h',title:'标题<script>&',original_title:'原问题',version:1,created_at:'2026-11-08T00:00:00Z',updated_at:'2026-11-08T00:00:00Z',pinned_at:null,hit_count:3,result_status:'ok'};
const detail={entry,q:'saved original',k:7,search_mode:'document',document_id:'doc',target_available:true,profile_id:'p',index_generation:'i',current_scope_version:'current',scope_version:'old',timings_ms:{search:123},items:[],unavailable_count:3};
const panel={response:{items:[entry],next_offset:10},offset:0,busy:false,opening:null,actionBusy:false,notice:'',error:'',intent:null,selectedId:'h',onOpen(){},onMenu(){},onClose(){},onSubmit(){},onRefresh(){},onPrevious(){},onNext(){}};

test('history local-day groups preserve server order and separate pinned entries',()=>{
 const now=new Date(2026,10,8,12);const stamp=(days)=>new Date(2026,10,8-days,9).toISOString();
 const items=[{...entry,history_id:'pin',pinned_at:'now',created_at:stamp(30)},...['today','yesterday','week','old'].map((id,i)=>({...entry,history_id:id,created_at:stamp([0,1,3,20][i])}))];
 const groups=groupHistories(items,now);assert.deepEqual(Array.from(groups,g=>g.label),['置顶','今天','昨天','过去7天','更早']);assert.equal(groups[0].entries[0].history_id,'pin');assert.equal(historyDate('2026-11-08T00:00:00').toISOString(),'2026-11-08T00:00:00.000Z');
});
test('history reference rendering preserves gaps and original scores without inventing hits',()=>{
 const hit={page_id:'page',page_rank:3,page_score:1.234,document_name:'Current name',page_number:2};const data={...detail,items:[hit]};const result=historyResult(data);assert.equal(result.items,data.items);assert.equal(result.scope_version,'current');const markup=render(RetrievalResults,{result,selected:null,onSelect(){},historical:true});assert.match(markup,/>03</);assert.match(markup,/排名可能不连续/);assert.ok(!markup.includes('>01<'));
 const empty=render(RetrievalResults,{result:historyResult(detail),selected:null,onSelect(){},historical:true});assert.match(empty,/历史暂无可用/);assert.match(empty,/没有自动重新检索/);
});
test('history sidebar escapes titles, exposes selected row, menus and10-row pagination',()=>{
 const markup=render(HistorySidebar,panel);assert.match(markup,/标题&lt;script&gt;&amp;/);assert.ok(!markup.includes('<script>'));assert.match(markup,/aria-haspopup="menu"/);assert.match(markup,/aria-current="true"/);assert.match(markup,/仅本人 · 每页10条/);assert.match(markup,/aria-label="历史分页"/);
 const shell={username:'user',role:'user',question:'',submittedQuestion:'',busy:false,notice:'',result:null,selected:null,image:null,imageBusy:false,imageError:'',searchMode:'library',targetDocument:null,onModeChange(){},onQuestionChange(){},onSearch(){},onSelect(){},onNewSearch(){},onLogout(){},historyPanel:panel};
 assert.equal((render(WorkspaceShell,shell).match(/id="history-heading"/g)||[]).length,1);
});
test('history dialogs require plain title or explicit deletion and disclose original PDF preservation',()=>{
 for(const kind of ['rename','delete']){const markup=render(HistoryDialog,{intent:{entry,kind},busy:false,error:'',onClose(){},onSubmit(){}});assert.ok(markup.indexOf('>取消</button>')<markup.indexOf('type="submit"'));if(kind==='rename'){assert.match(markup,/name="title"/);assert.match(markup,/maxLength="100"/i);assert.match(markup,/原问题和原文档名保持不变/);}else{assert.match(markup.match(/<input[^>]*name="confirmed"[^>]*>/)[0],/required=""/);assert.match(markup,/不删除原PDF/);assert.match(markup,/最小请求标记和操作事件仍保留/);}}
});
test('opening unavailable single-document history restores original k without falling back to library search',()=>{
 const unavailable={...detail,document_id:null,target_available:false};assert.equal(canRepeatHistory(unavailable),false);const banner=render(HistoryBanner,{detail:unavailable,busy:false,onRepeat(){}});assert.match(banner,/不会自动切换到文档库/);assert.match(banner,/type="button"[^>]*disabled=""/);assert.match(banner,/原返回数 7/);
 const composer=render(QueryComposer,{question:'original',busy:false,inputRef:{current:null},onQuestionChange(){},onSearch(){},searchMode:'document',queryK:7,restoredTarget:{id:null,available:false}});assert.match(composer,/value="7" selected=""/);assert.match(composer,/type="submit" disabled=""/);
});
test('unconfirmed submission disables new search without claiming active inference',()=>{
 const markup=render(QueryComposer,{question:'q',busy:false,pending:true,inputRef:{current:null},onQuestionChange(){},onSearch(){}});
 assert.match(markup,/type="submit" disabled=""/);assert.match(markup,/先核对提交/);assert.ok(!markup.includes('检索中'));
});
