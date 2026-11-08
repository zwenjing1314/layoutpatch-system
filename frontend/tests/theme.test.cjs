const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function fixture(saved, failRead=false, failWrite=false) {
  const events=new Map(), writes=[], document={documentElement:{dataset:{theme:'dark'}}};
  const storage={getItem(){if(failRead)throw Error('blocked');return saved;},setItem(key,value){if(failWrite)throw Error('blocked');writes.push({key,value});}};
  const window={localStorage:storage,addEventListener(k,v){events.set(k,v);},removeEventListener(k,v){if(events.get(k)===v)events.delete(k);}};
  const ctx={exports:{},window,document,localStorage:storage};
  const js=ts.transpileModule(fs.readFileSync('lib/theme.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  vm.runInNewContext(js,ctx);
  return {...ctx,exports:ctx.exports,writes,events,boot(){vm.runInNewContext(ctx.exports.THEME_BOOTSTRAP,ctx);}};
}
test('first paint honors only exact theme preferences; missing and malformed values use dark',()=>{
  for(const value of [null,'','system','LIGHT','<script>','{"theme":"light"}','light','dark']){
    const f=fixture(value);f.boot();assert.equal(f.document.documentElement.dataset.theme,value==='light'?'light':'dark');assert.equal(f.exports.serverTheme(),'dark');assert.equal(f.writes.length,0);
  }
});
test('blocked reads boot safely to dark without persisting anything',()=>{
  const f=fixture('light',true);assert.doesNotThrow(()=>f.boot());assert.equal(f.exports.currentTheme(),'dark');assert.deepEqual(f.writes,[]);
});
test('toggling persists only a non-sensitive theme and publishes current document state',()=>{
  const f=fixture('dark');f.boot();let seen=[];const stop=f.exports.subscribeTheme(()=>seen.push(f.exports.currentTheme()));
  f.exports.changeTheme('light');f.exports.changeTheme('dark');assert.deepEqual(seen,['light','dark']);assert.deepEqual(f.writes,[{key:'layoutpatch-theme',value:'light'},{key:'layoutpatch-theme',value:'dark'}]);stop();assert.equal(f.events.size,0);
});
test('blocked writes still update the current page and subscribers',()=>{
  const f=fixture(null,false,true);f.boot();let notifications=0;const stop=f.exports.subscribeTheme(()=>notifications++);
  assert.doesNotThrow(()=>f.exports.changeTheme('light'));assert.equal(f.exports.currentTheme(),'light');assert.equal(notifications,1);assert.deepEqual(f.writes,[]);stop();
});
test('storage updates ignore unrelated or invalid values; clear returns to dark without writing',()=>{
  const f=fixture('dark');let count=0;const stop=f.exports.subscribeTheme(()=>count++),send=f.events.get('storage');
  send({key:'private-query',newValue:'light'});send({key:'layoutpatch-theme',newValue:'invalid'});assert.equal(count,0);
  send({key:'layoutpatch-theme',newValue:'light'});assert.equal(f.exports.currentTheme(),'light');
  send({key:null,newValue:null});assert.equal(f.exports.currentTheme(),'dark');assert.equal(count,2);assert.deepEqual(f.writes,[]);stop();
});
test('pre-hydration light snapshot differs from stable server default; no shared app state or request is required',()=>{
  const f=fixture('light');f.boot();assert.equal(f.exports.currentTheme(),'light');assert.equal(f.exports.serverTheme(),'dark');
  const first=()=>{},second=()=>{};const a=f.exports.subscribeTheme(first),b=f.exports.subscribeTheme(second);a();assert.equal(f.events.size,1);b();assert.equal(f.events.size,0);
});
