const { test } = require('node:test');
const assert = require('node:assert/strict');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { loadTs } = require('./load-workspace.cjs');
const { matchesRegionPage,validRegions,privateCropPath,inferenceFailed } = loadTs('lib/region-state.ts');
const { RegionControls,RegionCanvas } = loadTs('components/workspace/region-evidence.tsx');
const { RequestGeneration } = loadTs('lib/workspace-lifecycle.ts');
const hit={page_id:'page',document_id:'doc',document_version_id:'v',page_number:2,width_px:1000,height_px:1400,render_sha256:'render',document_name:'test.pdf'};
const item={candidate_id:'page:block:3',layout_id:3,rank:1,score:2.5,type:'table',bbox:[10,20,200,300],crop_url:'/safe'};
const response={...hit,index_generation:'idx',status:'ready',items:[item],model_profile_sha256:'abc',candidate_hash:'def'};
const props={state:response,response,chosen:3,busy:false,error:'',crop:null,cropBusy:false,cropError:'',onRefresh(){},onParse(){},onLocate(){},onChoose(){},onCrop(){}};
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));

test('regions bind every page/version/render/index/dimension field',()=>{
  assert.equal(matchesRegionPage(response,hit,'idx'),true);
  for(const key of ['page_id','document_id','document_version_id','page_number','width_px','height_px','render_sha256'])assert.equal(matchesRegionPage({...response,[key]:'other'},hit,'idx'),false);
  assert.equal(matchesRegionPage(response,hit,'other'),false);
});
test('bad boxes, repeated IDs, nonfinite scores and ranks are rejected',()=>{
  assert.equal(validRegions(response),true);
  for(const patch of [{score:NaN},{score:Infinity},{rank:2},{candidate_id:'other:block:3'},{bbox:[0,0,1001,200]},{bbox:[3,3,3,5]},{bbox:[0,NaN,3,5]}])assert.equal(validRegions({...response,items:[{...item,...patch}]}),false);
  assert.equal(validRegions({...response,items:[item,{...item,rank:2}]}),false);
  assert.equal(validRegions({...response,items:[]}),false);
});
test('crop URL accepts only the exact private proxy format',()=>{
  const id='11111111-1111-1111-1111-111111111111',hash='a'.repeat(64);
  const path=`/pages/${id}/regions/3/crop?task=${id}&candidate_hash=${hash}&model=${hash}&token=${hash}`;
  assert.equal(privateCropPath(path),'/api'+path);
  for(const bad of ['https://example.com'+path,'//evil'+path,path+'&token=bad',path+'/../','data:image/png;base64,test'])assert.throws(()=>privateCropPath(bad));
});
test('inference retry stays distinct from parser retry and original image remains',()=>{
  const failed={...response,status:'failed',error_code:'REGION_INFERENCE_FAILED',can_parse:true};
  assert.equal(inferenceFailed(failed),true);
  let markup=render(RegionControls,{regions:{...props,state:failed,response:null}});
  assert.match(markup,/重试定位证据/);assert.ok(!markup.includes('重试文档解析'));assert.match(markup,/原图仍可阅读/);
  markup=render(RegionControls,{regions:{...props,state:{...failed,error_code:'PARSER_FAILED'},response:null}});
  assert.match(markup,/重试文档解析/);assert.ok(!markup.includes('重试定位证据'));
});
test('SVG and PNG share original-pixel viewBox and expose all three zoom levels',()=>{
  const markup=render(RegionCanvas,{selected:hit,image:'blob:private',regions:props});
  assert.match(markup,/viewBox="0 0 1000 1400"/);assert.match(markup,/x="10" y="20" width="190" height="280"/);
  for(const zoom of ['50%','100%','150%'])assert.ok(markup.includes(zoom));
  assert.match(markup,/第 2 页候选 3 高亮/);
  assert.ok(!render(RegionCanvas,{selected:{...hit,render_sha256:'new'},image:'blob:new',regions:props}).includes('<rect'));
});
test('region and crop responses arriving after scope reset are rejected independently',async()=>{
  const scope=new RequestGeneration(),crop=new RequestGeneration();let cancel=0;
  const old=scope.current(),oldCrop=crop.current();scope.track(()=>cancel++);crop.track(()=>cancel++);
  scope.reset();crop.reset();await Promise.resolve();
  assert.equal(scope.accepts(old),false);assert.equal(crop.accepts(oldCrop),false);assert.equal(cancel,2);
});
