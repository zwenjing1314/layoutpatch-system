"use client";
import { useCallback,useEffect,useRef,useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError,DeletionService } from '@/lib/api/generated';
import type { DeletionDocument,DeletionList } from '@/lib/api/generated';
import { RequestGeneration } from './workspace-lifecycle';
import { boundedTaskRequest } from './task-state';

export function deletionFailure(error: unknown) {
  if(error instanceof ApiError){
    if(error.status===409)return '文档或清理尝试已变化，请刷新并重新核对。';
    if(error.status===404)return '该文档不在本人删除范围，请刷新列表。';
    if(error.status===422)return '请核对文档版本和操作确认。';
  }
  return '操作结果尚未确认。已清理旧结果，请先刷新列表核对，不要直接重复提交。';
}

type Options={enabled:boolean;userId:string|null;csrfToken?:string;onSessionError:(e:unknown)=>void;onChanged:()=>void};
export function useDeletion(options:Options){
  const current=useRef(options);current.current=options;
  const lists=useRef(new RequestGeneration()),actions=useRef(new RequestGeneration()),pending=useRef(false);
  const [response,setResponse]=useState<DeletionList|null>(null),[offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
  const [busy,setBusy]=useState(false),[actionBusy,setActionBusy]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState('');
  const [intent,setIntent]=useState<DeletionDocument|null>(null);
  const reset=useCallback(()=>{lists.current.reset();actions.current.reset();pending.current=false;setResponse(null);setOffset(0);setBusy(false);setActionBusy(false);setNotice('');setError('');setIntent(null);},[]);
  function denied(e:unknown){if(e instanceof ApiError&&(e.status===401||e.status===403)){reset();current.current.onSessionError(e);return true;}return false;}
  function reload(){lists.current.reset();setResponse(null);setRefresh(v=>v+1);}
  useEffect(()=>{reset();return()=>{lists.current.reset();actions.current.reset();pending.current=false;};},[options.enabled,options.userId,reset]);
  useEffect(()=>{
    if(!options.enabled||!options.userId)return;
    const stamp=lists.current.reset();setBusy(true);setResponse(null);setError('');
    void (async()=>{try{
      const data=await boundedTaskRequest(DeletionService.listDeletionDocuments(10,offset),lists.current,15_000);
      if(!lists.current.accepts(stamp)||!current.current.enabled)return;
      if(offset>0&&!data.items.length){setOffset(0);return;}setResponse(data);
    }catch(e){if(lists.current.accepts(stamp)&&current.current.enabled&&!denied(e))setError('删除与清理列表暂时无法确认，请刷新。');}
    finally{if(lists.current.accepts(stamp))setBusy(false);}})();
    return()=>{lists.current.reset();};
    // Callbacks use current identity refs; no retrieval request is cancelled here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[options.enabled,options.userId,offset,refresh]);
  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    if(pending.current||!intent||!current.current.enabled||!current.current.csrfToken)return;
    if(new FormData(event.currentTarget).get('confirmed')!=='yes'){setError('请先核对删除影响并确认。');return;}
    const captured=intent,stamp=actions.current.reset();pending.current=true;setActionBusy(true);setError('');setNotice('');lists.current.reset();setBusy(false);
    try{
      const request=captured.status==='deleted'
        ?DeletionService.retryDocumentCleanup(captured.document_id,{attempt:captured.attempt!,confirmed:true})
        :DeletionService.deleteOwnDocument(captured.document_id,{document_version_id:captured.document_version_id,access_version:captured.access_version,confirmed:true});
      await boundedTaskRequest(request,actions.current,15_000);
      if(!actions.current.accepts(stamp)||!current.current.enabled)return;
      setIntent(null);setNotice(captured.status==='deleted'?'已请求重试残留清理，文档仍不可读取。请刷新查看状态。':'已撤销文档访问，后台开始清理。请刷新查看清理状态；清理失败也不会恢复读取。');
      current.current.onChanged();reload();
    }catch(e){
      if(!actions.current.accepts(stamp)||!current.current.enabled||denied(e))return;
      setIntent(null);setNotice(deletionFailure(e));current.current.onChanged();reload();
    }finally{if(actions.current.accepts(stamp)){pending.current=false;setActionBusy(false);}}
  }
  return {reset,panel:{response,offset,busy,actionBusy,notice,error,intent,
    onRefresh(){if(!pending.current)reload();},
    onPrevious(){if(!pending.current&&!busy&&offset>0){lists.current.reset();setResponse(null);setOffset(v=>Math.max(0,v-10));}},
    onNext(){if(!pending.current&&!busy&&response?.next_offset!=null){lists.current.reset();setResponse(null);setOffset(response.next_offset);}},
    onOpen(doc:DeletionDocument){if(!pending.current&&current.current.enabled&&(doc.status!=='deleted'||doc.cleanup_status==='failed')){setIntent(doc);setNotice('');setError('');}},
    onClose(){if(!pending.current){setIntent(null);setError('');}},onSubmit:submit}};
}
export type DeletionProps=ReturnType<typeof useDeletion>['panel'];
