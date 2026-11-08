const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const { loadTs } = require('./load-workspace.cjs');

// Minimal scheduler controls cancellation races; real React/dialogs are checked in the browser.
function harness(file, exported, initial = {}) {
  const slots = [], effects = [], calls = [], sessions = [], opened = [], updated = [], unavailable = [], results = [], starts = [];
  let cursor = 0, dirty = true, result, uuids = 0;
  let options = { enabled: true, userId: 'self', selectedId: null,
    onSessionError: e => sessions.push(e), onOpening() {}, onOpened: d => opened.push(d), onUpdated: d => updated.push(d), onUnavailable: id => unavailable.push(id),
    onStart: body => starts.push(body), onResult: (detail,replayed) => results.push({detail,replayed}), ...initial };
  const equal=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
  const react={
    useState(value){const i=cursor++;if(!slots[i])slots[i]={value:typeof value==='function'?value():value};return[slots[i].value,next=>{const v=typeof next==='function'?next(slots[i].value):next;if(!Object.is(v,slots[i].value)){slots[i].value=v;dirty=true;}}];},
    useRef(value){const i=cursor++;if(!slots[i])slots[i]={current:value};return slots[i];},
    useCallback(value,deps){const i=cursor++;if(!slots[i]||!equal(slots[i].deps,deps))slots[i]={value,deps};return slots[i].value;},
    useEffect(callback,deps){const i=cursor++;if(!slots[i]||!equal(slots[i].deps,deps))effects.push({i,callback,deps});},
  };
  class ApiError extends Error { constructor(status,detail=''){super('API');this.status=status;this.body={detail};} }
  const service=new Proxy({},{get:(_,method)=>(...args)=>{
    let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});
    const call={method,args,resolve,reject,cancelled:0};promise.cancel=()=>call.cancelled++;calls.push(call);return promise;
  }});
  const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const context={exports:{},crypto:{randomUUID:()=>`00000000-0000-4000-8000-${String(++uuids).padStart(12,'0')}`},
    FormData:class{constructor(form){this.data={...form.data};}get(k){return this.data[k]??null;}},
    require(name){if(name==='react')return react;if(name==='./api/generated')return{ApiError,AuditService:service,IndexesService:service};
      if(['./workspace-lifecycle','./task-state','./history-state'].includes(name))return loadTs('lib/'+name.slice(2)+'.ts');
      throw new Error('Unexpected hook dependency '+name);}};
  vm.runInNewContext(source,context);
  function render(){for(let n=0;dirty||effects.length;n++){
    assert.ok(n<30,'hook settled');if(dirty){dirty=false;cursor=0;result=context.exports[exported](options);}
    const queue=effects.splice(0);for(const e of queue)slots[e.i]?.cleanup?.();for(const e of queue)slots[e.i]={deps:e.deps,cleanup:e.callback()};
  }return result;}
  return {calls,sessions,opened,updated,unavailable,results,starts,ApiError,
    get value(){return render();},get panel(){return render().panel;},
    update(next){options={...options,...next};dirty=true;return render();},
    async settle(){for(let i=0;i<16;i++){await Promise.resolve();render();}},
    close(){for(const slot of slots)slot?.cleanup?.();},
  };
}
module.exports={harness};
