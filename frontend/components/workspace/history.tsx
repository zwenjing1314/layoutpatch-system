"use client";
import { useEffect, useRef, useState } from 'react';
import type { HistoryDetail, HistorySummary } from '@/lib/api/generated';
import type { HistoryIntent, HistoryProps } from '@/lib/use-history';
import { canRepeatHistory, groupHistories, historyDate } from '@/lib/history-state';

function HistoryMenu({entry,disabled,onChoose}:{entry:HistorySummary;disabled:boolean;onChoose:HistoryProps['onMenu']}) {
  const [open,setOpen]=useState(false),root=useRef<HTMLDivElement|null>(null),trigger=useRef<HTMLButtonElement|null>(null);
  useEffect(()=>{
    if(!open)return;
    root.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
    const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);
  },[open]);
  useEffect(()=>setOpen(false),[entry.version,disabled]);
  return <div ref={root} className="ws-history-menu" onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOpen(false);}} onKeyDown={e=>{
    if(e.key==='Escape'&&open){e.preventDefault();e.stopPropagation();setOpen(false);trigger.current?.focus();}
    if(!open||!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;
    e.preventDefault();const nodes=Array.from(root.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')??[]);
    const at=nodes.indexOf(document.activeElement as HTMLButtonElement);
    nodes[e.key==='Home'?0:e.key==='End'?nodes.length-1:(at+(e.key==='ArrowUp'?-1:1)+nodes.length)%nodes.length]?.focus();
  }}>
    <button ref={trigger} type="button" aria-label={`历史操作：${entry.title}`} aria-haspopup="menu" aria-expanded={open} disabled={disabled} onClick={()=>setOpen(v=>!v)}>⋯</button>
    {open&&<div role="menu" aria-label="历史操作">{(['rename','pin','delete'] as const).map(kind=><button key={kind} type="button" role="menuitem" onClick={()=>{setOpen(false);onChoose(entry,kind);}}>
      {kind==='rename'?'重命名':kind==='pin'?entry.pinned_at?'取消置顶':'置顶':'删除历史'}
    </button>)}</div>}
  </div>;
}

export function HistoryDialog({intent,busy,error,onClose,onSubmit}:{intent:HistoryIntent;busy:boolean;error:string;onClose:()=>void;onSubmit:HistoryProps['onSubmit']}) {
  const node=useRef<HTMLDialogElement|null>(null),cancel=useRef<HTMLButtonElement|null>(null),form=useRef<HTMLFormElement|null>(null);
  const deleting=intent.kind==='delete';
  useEffect(()=>{const dialog=node.current;dialog?.showModal();cancel.current?.focus();return()=>{form.current?.reset();dialog?.close();};},[]);
  return <dialog ref={node} className="ws-account-dialog" aria-labelledby="history-dialog-title" aria-describedby="history-impact" onKeyDown={e=>{if(e.key==='Escape')e.stopPropagation();}} onCancel={e=>{e.preventDefault();if(!busy)onClose();}}>
    <form ref={form} onSubmit={onSubmit}><p className="ws-eyebrow">仅本人历史</p><h2 id="history-dialog-title">{deleting?'删除历史':'重命名历史'}</h2>
      <p className="ws-account-target"><strong>{intent.entry.title}</strong></p>
      <p id="history-impact">{deleting?'仅删除本人的问题、标题和命中引用，不删除原PDF，不影响其他用户。最小请求标记和操作事件仍保留；已交付的内容和独立备份无法远程收回。':'只修改这条历史的显示标题，原问题和原文档名保持不变。标题为1—100字单行纯文本。'}</p>
      {deleting?<label className="ws-account-confirm"><input name="confirmed" type="checkbox" value="yes" required disabled={busy}/><span>我确认删除这条本人历史，删除后不能从历史恢复。</span></label>:<label className="ws-history-title-field">历史标题<input name="title" type="text" required minLength={1} maxLength={100} defaultValue={intent.entry.title} disabled={busy}/></label>}
      {error&&<p role="alert" className="ws-task-warning">{error}</p>}{busy&&<p role="status">正在提交，请勿重复操作。停止等待不表示服务端已取消。</p>}
      <div className="ws-account-dialog-actions"><button ref={cancel} type="button" disabled={busy} onClick={onClose}>取消</button><button type="submit" disabled={busy} className={deleting?'ws-account-danger':undefined}>{busy?'提交中…':deleting?'确认删除历史':'保存标题'}</button></div>
    </form>
  </dialog>;
}

export function HistorySidebar(props:HistoryProps) {
  const heading=useRef<HTMLHeadingElement|null>(null),hadDialog=useRef(false);
  useEffect(()=>{if(hadDialog.current&&!props.intent)heading.current?.focus();hadDialog.current=!!props.intent;},[props.intent]);
  return <section className="ws-history" aria-labelledby="history-heading">
    <header><h2 id="history-heading" ref={heading} tabIndex={-1}>检索历史</h2><button type="button" aria-label="刷新历史" onClick={props.onRefresh} disabled={props.busy||props.actionBusy}>↻</button></header>
    <p className="ws-history-help">仅本人 · 每页10条 · 本页按保存日期分组</p>
    {props.notice&&<p className="ws-history-feedback" role="status">{props.notice}</p>}{props.error&&<p className="ws-history-feedback" role="alert">{props.error}</p>}
    {props.busy&&<p role="status">正在读取历史…</p>}{props.opening&&<p role="status">正在核对历史引用，未执行新检索…</p>}
    {props.response&&!props.response.items.length&&<p className="ws-history-help" role="status">还没有保存的检索。提交一次实际检索后会出现在这里。</p>}
    <div className="ws-history-groups" aria-busy={props.busy}>{groupHistories(props.response?.items??[]).map(group=><section key={group.label} aria-label={group.label}>
      <h3>{group.label}</h3><ul>{group.entries.map(entry=><li key={entry.history_id} className={entry.history_id===props.selectedId?'is-selected':''}>
        <button type="button" className="ws-history-open" title={entry.title} aria-current={entry.history_id===props.selectedId?'true':undefined} disabled={props.actionBusy} onClick={()=>props.onOpen(entry)}>
          <strong>{entry.title}</strong><small><time dateTime={entry.created_at}>{historyDate(entry.created_at).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'})}</time> · {entry.hit_count}项原命中</small>
        </button><HistoryMenu entry={entry} disabled={props.actionBusy||props.busy} onChoose={props.onMenu}/>
      </li>)}</ul>
    </section>)}</div>
    <nav className="ws-history-pagination" aria-label="历史分页"><button type="button" onClick={props.onPrevious} disabled={props.offset===0||props.busy||props.actionBusy}>上一页</button><span>{Math.floor(props.offset/10)+1}</span><button type="button" onClick={props.onNext} disabled={props.response?.next_offset==null||props.busy||props.actionBusy}>下一页</button></nav>
    {props.intent&&<HistoryDialog key={props.intent.kind+props.intent.entry.history_id+props.intent.entry.version} intent={props.intent} busy={props.actionBusy} error={props.error} onClose={props.onClose} onSubmit={props.onSubmit}/>}
  </section>;
}

export function HistoryBanner({detail,busy,onRepeat}:{detail:HistoryDetail;busy:boolean;onRepeat:()=>void}) {
  return <section className="ws-history-banner" aria-label="当前历史记录"><p className="ws-eyebrow">已保存的历史结果</p><h2>{detail.entry.title}</h2>
    <p><time dateTime={detail.entry.created_at}>{historyDate(detail.entry.created_at).toLocaleString('zh-CN')}</time> · 原返回数 {detail.k} · {detail.search_mode==='library'?'文档库':'单文档'}</p>
    <p>原问题与原排名保留；打开只核对当前权限，不执行模型。当前可用 {detail.items.length} 项，失效 {detail.unavailable_count} 项，原排名可能不连续。</p>
    {detail.search_mode==='document'&&<p>{detail.target_available?`原目标 ID ${detail.document_id}`:'原目标已不可用，请重新选择文档；不会自动切换到文档库。'}</p>}
    <details><summary>原计算身份与耗时</summary><p>profile {detail.profile_id}<br/>索引 {detail.index_generation}<br/>{Object.entries(detail.timings_ms).map(([key,value])=><span key={key}>{key}: {value.toFixed(1)} ms </span>)}</p></details>
    <button type="button" onClick={onRepeat} disabled={busy||!canRepeatHistory(detail)}>按原条件重新检索</button><small>明确提交才运行新检索并新建历史；当前授权范围可能已变化。</small>
  </section>;
}
