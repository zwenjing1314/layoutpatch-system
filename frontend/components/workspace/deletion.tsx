"use client";
import { useEffect,useRef } from 'react';
import type { DeletionDocument } from '@/lib/api/generated';
import type { DeletionProps } from '@/lib/use-deletion';

export function DeletionDialog({doc,busy,error,onClose,onSubmit}:{doc:DeletionDocument;busy:boolean;error:string;onClose:()=>void;onSubmit:DeletionProps['onSubmit']}){
  const dialog=useRef<HTMLDialogElement|null>(null),form=useRef<HTMLFormElement|null>(null),cancel=useRef<HTMLButtonElement|null>(null);
  const retrying=doc.status==='deleted';
  useEffect(()=>{const node=dialog.current;node?.showModal();cancel.current?.focus();return()=>{form.current?.reset();node?.close();};},[]);
  return <dialog ref={dialog} className="ws-account-dialog" aria-labelledby="deletion-dialog-title" aria-describedby="deletion-impact" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}>
    <form ref={form} onSubmit={onSubmit}><p className="ws-eyebrow">本人文档 · 不可恢复操作</p><h2 id="deletion-dialog-title">{retrying?'重试残留清理':'删除文档'}</h2>
      <p className="ws-account-target"><strong>{doc.display_name}</strong><small>ID {doc.document_id} · 授权版本 {doc.access_version}{retrying?` · 清理尝试 ${doc.attempt}`:''}</small></p>
      <p id="deletion-impact">{retrying?'文档已经不可读取。重试只继续清理残留，不会恢复文档或重新入库。':'确认后先撤销文档访问，旧检索、原图、区域和裁剪链接将失效；随后清理索引、原PDF、页图、候选、特征与缓存。删除无法撤销，需要时只能重新上传。'}</p>
      <p>后台会等待正在写入的任务结束再清理。清理失败仍不可读取，可刷新查看状态并重试。已交付浏览器的内容无法远程收回。</p>
      <label className="ws-account-confirm"><input name="confirmed" type="checkbox" value="yes" required disabled={busy}/><span>我已核对本人文档与影响，确认{retrying?'重试清理':'永久删除'}。</span></label>
      {error&&<p role="alert" className="ws-task-warning">{error}</p>}{busy&&<p role="status">正在提交，请勿重复操作。停止等待不表示服务器已取消。</p>}
      <div className="ws-account-dialog-actions"><button ref={cancel} type="button" onClick={onClose} disabled={busy}>取消</button><button type="submit" disabled={busy} className="ws-account-danger">{busy?'提交中…':retrying?'确认重试清理':'确认永久删除'}</button></div>
    </form></dialog>;
}

function label(doc:DeletionDocument){
  if(doc.status!=='deleted')return doc.status==='ready'?'可读取':'尚未就绪';
  return {queued:'访问已撤销 · 等待清理',running:'访问已撤销 · 清理中',failed:'不可读取 · 清理失败',completed:'不可读取 · 清理完成'}[doc.cleanup_status??'']??'不可读取';
}

export function DeletionPanel(props:DeletionProps){
  const heading=useRef<HTMLHeadingElement|null>(null),hadDialog=useRef(false);
  useEffect(()=>{if(hadDialog.current&&!props.intent)heading.current?.focus();hadDialog.current=!!props.intent;},[props.intent]);
  return <main className="ws-accounts-main" aria-labelledby="deletion-heading"><div className="ws-accounts-content">
    <header className="ws-accounts-heading"><div><p className="ws-eyebrow">本人文档 · 生命周期</p><h1 id="deletion-heading" ref={heading} tabIndex={-1}>删除与清理</h1><p>仅删除当前账号本人的文档，包括尚未就绪的上传。共享接收者及管理员均不能跨用户删除。</p></div></header>
    <div className="ws-accounts-toolbar"><p>每页10份 · 清理状态保留，可刷新恢复</p><button type="button" onClick={props.onRefresh} disabled={props.busy||props.actionBusy}>刷新列表</button></div>
    {props.notice&&<p className="ws-account-notice" role="status">{props.notice}</p>}{props.error&&<p className="ws-task-warning" role="alert">{props.error}</p>}
    {props.busy&&<p role="status">正在读取删除与清理列表…</p>}{props.response&&!props.response.items.length&&<p role="status">暂无本人文档。</p>}
    <section className="ws-account-cards" aria-label="本人删除与清理文档" aria-busy={props.busy}>{props.response?.items.map(doc=><article className="ws-account-card" key={doc.document_id}>
      <div className="ws-account-card-heading"><h2>{doc.display_name}</h2><span className="ws-account-badge">{label(doc)}</span></div>
      <p className="ws-account-id">ID {doc.document_id}</p><p className="ws-account-role">授权版本 {doc.access_version}{doc.attempt?` · 清理尝试 ${doc.attempt}`:''}</p>
      {doc.cleanup_status==='failed'&&<p className="ws-task-warning">残留尚未清理完，文档仍不可读取。请重试；若再次失败，请联系本地维护人员核查存储和索引。</p>}
      {doc.status==='deleted'&&doc.cleanup_status!=='failed'?null:<div className="ws-account-actions"><button type="button" className="ws-account-danger" disabled={props.busy||props.actionBusy} onClick={()=>props.onOpen(doc)}>{doc.status==='deleted'?'重试残留清理':'删除文档'}</button></div>}
    </article>)}</section>
    <nav className="ws-account-pagination" aria-label="删除与清理分页"><button type="button" disabled={props.offset===0||props.busy||props.actionBusy} onClick={props.onPrevious}>上一页</button><span>第 {Math.floor(props.offset/10)+1} 页</span><button type="button" disabled={props.response?.next_offset==null||props.busy||props.actionBusy} onClick={props.onNext}>下一页</button></nav>
  </div>{props.intent&&<DeletionDialog key={props.intent.document_id+':'+props.intent.access_version+':'+props.intent.attempt} doc={props.intent} busy={props.actionBusy} error={props.error} onClose={props.onClose} onSubmit={props.onSubmit}/>}</main>;
}
