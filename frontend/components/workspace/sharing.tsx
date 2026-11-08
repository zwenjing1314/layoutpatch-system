"use client";
import { useEffect,useRef } from 'react';
import type { SharingDocument } from '@/lib/api/generated';
import type { SharingProps } from '@/lib/use-sharing';

export function SharingDialog({doc,busy,error,onClose,onSubmit}:{doc:SharingDocument;busy:boolean;error:string;onClose:()=>void;onSubmit:SharingProps['onSubmit']}){
  const dialog=useRef<HTMLDialogElement|null>(null),form=useRef<HTMLFormElement|null>(null),cancel=useRef<HTMLButtonElement|null>(null);
  const withdrawing=doc.visibility==='shared';
  useEffect(()=>{const node=dialog.current;node?.showModal();cancel.current?.focus();return()=>{form.current?.reset();node?.close();};},[]);
  return <dialog ref={dialog} className="ws-account-dialog" aria-labelledby="sharing-dialog-title" aria-describedby="sharing-impact" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}>
    <form ref={form} onSubmit={onSubmit}><p className="ws-eyebrow">确认共享范围</p><h2 id="sharing-dialog-title">{withdrawing?'撤回共享':'发布共享'}</h2>
      <p className="ws-account-target"><strong>{doc.display_name}</strong><small>ID {doc.document_id} · 文档版本 {doc.version??'未就绪'} · 授权版本 {doc.access_version}</small></p>
      <p id="sharing-impact">{withdrawing?'文档将改为私有，仅本人可读。其他用户后续检索、原图、区域和裁剪请求会重新拒绝；已交付给浏览器的内容无法远程收回。':'这份本人文档将向所有已登录且完成首改的用户开放读取，包括页面原图、区域定位及裁剪。其他用户不能执行解析或入库管理。'}</p>
      <p>不会删除文档或重新编码。每次真实发布/撤回都会更新授权版本；重新发布不会复活旧图片和裁剪链接。</p>
      <label className="ws-account-confirm"><input name="confirmed" type="checkbox" value="yes" required disabled={busy}/><span>我已核对文档和共享范围，确认{withdrawing?'撤回':'发布'}。</span></label>
      {error&&<p role="alert" className="ws-task-warning">{error}</p>}{busy&&<p role="status">正在提交，请勿重复操作。停止等待不表示服务器已取消。</p>}
      <div className="ws-account-dialog-actions"><button ref={cancel} type="button" onClick={onClose} disabled={busy}>取消</button><button type="submit" disabled={busy} className={withdrawing?'ws-account-danger':''}>{busy?'提交中…':withdrawing?'确认撤回共享':'确认发布共享'}</button></div>
    </form></dialog>;
}
export function SharingPanel(props:SharingProps){
  const heading=useRef<HTMLHeadingElement|null>(null),hadDialog=useRef(false);
  useEffect(()=>{if(hadDialog.current&&!props.intent)heading.current?.focus();hadDialog.current=!!props.intent;},[props.intent]);
  return <main className="ws-accounts-main" aria-labelledby="sharing-heading"><div className="ws-accounts-content">
    <header className="ws-accounts-heading"><div><p className="ws-eyebrow">本人文档 · 授权管理</p><h1 id="sharing-heading" ref={heading} tabIndex={-1}>共享管理</h1><p>仅管理当前管理员本人上传的文档，不读取或发布他人的私有文档。</p></div></header>
    <div className="ws-accounts-toolbar"><p>每页10份 · 发布前核对共享范围</p><button type="button" onClick={props.onRefresh} disabled={props.busy||props.actionBusy}>刷新列表</button></div>
    {props.notice&&<p className="ws-account-notice" role="status">{props.notice}</p>}{props.error&&<p className="ws-task-warning" role="alert">{props.error}</p>}
    {props.busy&&<p role="status">正在读取共享管理列表…</p>}{props.response&&!props.response.items.length&&<p role="status">暂无本人可管理文档。先在上传与任务中完成本人PDF入库，再刷新。</p>}
    <section className="ws-account-cards" aria-label="本人共享管理文档" aria-busy={props.busy}>{props.response?.items.map(doc=><article className="ws-account-card ws-sharing-card" key={doc.document_id}>
      <div className="ws-account-card-heading"><h2>{doc.display_name}</h2><span className="ws-account-badge">{doc.visibility==='shared'?'已共享':'仅本人'}</span></div>
      <p className="ws-account-role">文档版本 {doc.version??'未就绪'} · {doc.page_count??0} 页 · 授权版本 {doc.access_version}</p><p className="ws-account-id">ID {doc.document_id}</p>
      {!doc.can_publish&&doc.visibility!=='shared'&&<p className="ws-account-help">文档尚未完整就绪，暂不可发布。</p>}
      <div className="ws-account-actions"><button type="button" disabled={props.busy||props.actionBusy||(!doc.can_publish&&doc.visibility!=='shared')} onClick={()=>props.onOpen(doc)}>{doc.visibility==='shared'?'撤回共享':'发布共享'}</button></div>
    </article>)}</section>
    <nav className="ws-account-pagination" aria-label="共享管理分页"><button type="button" disabled={props.offset===0||props.busy||props.actionBusy} onClick={props.onPrevious}>上一页</button><span>第 {Math.floor(props.offset/10)+1} 页</span><button type="button" disabled={props.response?.next_offset==null||props.busy||props.actionBusy} onClick={props.onNext}>下一页</button></nav>
  </div>{props.intent&&<SharingDialog key={props.intent.document_id+':'+props.intent.access_version} doc={props.intent} busy={props.actionBusy} error={props.error} onClose={props.onClose} onSubmit={props.onSubmit}/>}</main>;
}
