"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, IndexesService } from './api/generated';
import type { IndexManagementState, ManagedIndex } from './api/generated';
import { RequestGeneration } from './workspace-lifecycle';
import { boundedTaskRequest } from './task-state';

type Action='verify'|'rebuild'|'activate';
type Options={enabled:boolean;userId:string|null;csrfToken?:string;onSessionError:(e:unknown)=>void;onChanged:()=>void};
export function useIndexes(options:Options){
  const current=useRef(options);current.current=options;
  const lists=useRef(new RequestGeneration()),actions=useRef(new RequestGeneration()),pending=useRef(false);
  const [response,setResponse]=useState<IndexManagementState|null>(null),[offset,setOffset]=useState(0),[operationOffset,setOperationOffset]=useState(0),[refresh,setRefresh]=useState(0);
  const [busy,setBusy]=useState(false),[actionBusy,setActionBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const [intent,setIntent]=useState<{action:Action;index:ManagedIndex;active:string;epoch:number}|null>(null);
  const reset=useCallback(()=>{lists.current.reset();actions.current.reset();pending.current=false;setResponse(null);setOffset(0);setOperationOffset(0);setBusy(false);setActionBusy(false);setNotice('');setError('');setIntent(null);},[]);
  function denied(e:unknown){if(e instanceof ApiError&&(e.status===401||e.status===403)){reset();current.current.onSessionError(e);return true;}return false;}
  function reload(){lists.current.reset();setResponse(null);setIntent(null);setRefresh(v=>v+1);}
  useEffect(()=>{reset();return()=>{lists.current.reset();actions.current.reset();pending.current=false;};},[options.enabled,options.userId,reset]);
  useEffect(()=>{
    if(!options.enabled||!options.userId)return;
    const stamp=lists.current.reset();setBusy(true);setResponse(null);setError('');
    void(async()=>{try{
      const data=await boundedTaskRequest(IndexesService.getIndexManagement(offset,operationOffset),lists.current,15_000);
      if(lists.current.accepts(stamp)&&current.current.enabled){setResponse(data);if(offset>0&&!data.indexes.length)setOffset(0);if(operationOffset>0&&!data.operations.length)setOperationOffset(0);}
    }catch(e){if(lists.current.accepts(stamp)&&current.current.enabled&&!denied(e))setError('配置与索引状态暂时无法确认，请刷新。');}
    finally{if(lists.current.accepts(stamp))setBusy(false);}})();
    return()=>{lists.current.reset();};
  },[options.enabled,options.userId,offset,operationOffset,refresh]);
  async function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    if(pending.current||!intent||!current.current.enabled||!current.current.csrfToken)return;
    if(new FormData(e.currentTarget).get('confirmed')!=='yes'){setError('请核对索引与影响并勾选确认。');return;}
    const captured=intent,stamp=actions.current.reset();pending.current=true;setActionBusy(true);setNotice('');setError('');lists.current.reset();setBusy(false);
    const body={request_id:crypto.randomUUID(),index_id:captured.index.index_id,active_index_id:captured.active,index_epoch:captured.epoch,confirmed:true};
    try{
      const request=captured.action==='verify'?IndexesService.verifyIndexProfile(body):captured.action==='rebuild'?IndexesService.rebuildIndex(body):IndexesService.activateIndex(body);
      const result=await boundedTaskRequest(request,actions.current,240_000);
      if(!actions.current.accepts(stamp)||!current.current.enabled)return;
      setNotice(result.status==='completed'?(captured.action==='rebuild'?'候选索引重建并校验完成，当前活动代保持。请核对后单独激活。':captured.action==='activate'?'索引切换已确认，请重新检索获取当前结果。':'离线文件、实现与索引身份验证通过，未执行推理。'):'操作仍在运行或未完成，请刷新操作记录核对。');
      current.current.onChanged();reload();
    }catch(error){
      if(!actions.current.accepts(stamp)||!current.current.enabled||denied(error))return;
      setNotice(error instanceof ApiError&&error.status===409?'索引、语料或活动版本已变化，本次未覆盖新状态。请刷新核对。':'操作结果尚未确认。请刷新操作记录和活动代核对；没有自动重试。');
      current.current.onChanged();reload();
    }finally{if(actions.current.accepts(stamp)){pending.current=false;setActionBusy(false);}}
  }
  return {reset,panel:{response,offset,operationOffset,busy,actionBusy,notice,error,intent,
    onRefresh(){if(!pending.current)reload();},
    onPage(next:number,operations=false){if(!pending.current&&!busy){lists.current.reset();setResponse(null);setIntent(null);if(operations)setOperationOffset(next);else setOffset(next);}},
    onOpen(action:Action,index:ManagedIndex){if(!pending.current&&response&&current.current.enabled){setIntent({action,index,active:response.active_index_id,epoch:response.index_epoch});setError('');setNotice('');}},
    onClose(){if(!pending.current){setIntent(null);setError('');}},onSubmit:submit}};
}
export type IndexesProps=ReturnType<typeof useIndexes>['panel'];
