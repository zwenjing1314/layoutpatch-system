"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, AuditService } from './api/generated';
import type { AuditEventList, AuditTaskList } from './api/generated';
import { RequestGeneration } from './workspace-lifecycle';
import { boundedTaskRequest } from './task-state';

type Tab = 'events' | 'tasks';
type Filters = { start: string; end: string; source: string; state: string; actor: string; target: string };
const DAY = 86400000;
export function auditDefaults(): Filters {
  const today = Date.now();
  return { start: new Date(today-6*DAY).toISOString().slice(0,10), end: new Date(today).toISOString().slice(0,10), source:'', state:'', actor:'', target:'' };
}
export function auditWindow(filters: Filters) {
  const since = Date.parse(filters.start+'T00:00:00Z')/1000, until = Date.parse(filters.end+'T00:00:00Z')/1000+86400;
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!Number.isFinite(since) || !Number.isFinite(until) || since < 0 || until <= since || until-since > 31*86400 ||
    [filters.actor,filters.target].some(v=>v&&!uuid.test(v))) throw new Error('INVALID_FILTER');
  return {since,until};
}

export function useAudit(options: { enabled:boolean; userId:string|null; onSessionError:(e:unknown)=>void }) {
  const current=useRef(options); current.current=options;
  const requests=useRef(new RequestGeneration()),scope=useRef<string|null>(null),owner=useRef(options.userId);
  const [tab,setTab]=useState<Tab>('events'),[filters,setFilters]=useState<Filters>(auditDefaults);
  const [offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
  const [response,setResponse]=useState<AuditEventList|AuditTaskList|null>(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[formKey,setFormKey]=useState(0);
  const reset=useCallback(()=>{requests.current.reset();scope.current=null;setResponse(null);setBusy(false);setError('');setNotice('');setOffset(0);setTab('events');setFilters(auditDefaults());setFormKey(v=>v+1);},[]);
  useEffect(()=>{if(!options.enabled||owner.current!==options.userId)reset();owner.current=options.userId;return()=>{requests.current.reset();};},[options.enabled,options.userId,reset]);
  useEffect(()=>{
    if(!options.enabled||!options.userId)return;
    const stamp=requests.current.reset();setBusy(true);setResponse(null);setError('');
    void(async()=>{
      try{
        const {since,until}=auditWindow(filters);
        const data=await boundedTaskRequest<AuditEventList|AuditTaskList>(tab==='events'
          ?AuditService.listAuditEvents(since,until,10,offset,filters.source as 'account'|'sharing'|'deletion'|'history'|'index'||undefined,filters.actor||undefined,filters.target||undefined,filters.state as 'success'|'noop'|'rejected'|'failed'||undefined)
          :AuditService.listAuditTasks(since,until,10,offset,filters.source as 'ingest'|'parsing'|'cleanup'|'search'|'index'||undefined,filters.state as Parameters<typeof AuditService.listAuditTasks>[5]||undefined,filters.actor||undefined,filters.target||undefined),requests.current,15_000);
        if(!requests.current.accepts(stamp)||!current.current.enabled)return;
        if(offset>0&&(scope.current!==data.scope_version||!data.items.length)){scope.current=null;setOffset(0);setNotice('列表已更新，已返回第一页，请重新核对。');return;}
        scope.current=data.scope_version;setResponse(data);
      }catch(e){
        if(!requests.current.accepts(stamp)||!current.current.enabled)return;
        if(e instanceof ApiError&&(e.status===401||e.status===403)){reset();current.current.onSessionError(e);return;}
        setError(e instanceof ApiError&&e.status===409?'列表在读取时发生变化，请刷新。':e instanceof ApiError&&e.status===422?'请核对日期范围（最多31天）和筛选ID。':'暂时无法确认查询结果，请刷新。');
      }finally{if(requests.current.accepts(stamp))setBusy(false);}
    })();
    return()=>{requests.current.reset();};
  },[options.enabled,options.userId,tab,filters,offset,refresh,reset]);
  function first(){requests.current.reset();scope.current=null;setResponse(null);setOffset(0);setNotice('');setError('');}
  return {reset,panel:{tab,filters,formKey,response,busy,error,notice,offset,
    onTab(next:Tab){if(tab!==next){first();setTab(next);setFilters(auditDefaults());setFormKey(v=>v+1);}},
    onSubmit(event:FormEvent<HTMLFormElement>){event.preventDefault();const data=new FormData(event.currentTarget);
      const next=Object.fromEntries(['start','end','source','state','actor','target'].map(k=>[k,String(data.get(k)??'').trim()])) as Filters;
      try{auditWindow(next);}catch{setError('请填写有效UTC日期，跨度最多31天；ID须为完整UUID。');return;}
      first();setFilters(next);
    },
    onRefresh(){first();setRefresh(v=>v+1);},
    onPrevious(){if(!busy&&offset>0){requests.current.reset();setResponse(null);setOffset(v=>Math.max(0,v-10));}},
    onNext(){if(!busy&&response?.next_offset!=null){requests.current.reset();setResponse(null);setOffset(response.next_offset);}},
  }};
}
export type AuditProps=ReturnType<typeof useAudit>['panel'];
