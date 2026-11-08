"use client";

import { useEffect, useRef } from "react";
import type { FormEvent } from "react";
import type { AccountList, AccountResponse } from "@/lib/api/generated";
import { accountActionLabel, accountImpact } from "@/lib/account-state";
import type { AccountAction, AccountIntent } from "@/lib/account-state";

export type AccountsProps = {
  userId: string; accounts: AccountList | null; listBusy: boolean; listError: string; notice: string; offset: number;
  intent: AccountIntent | null; dialogKey: number; dialogError: string; actionBusy: boolean;
  onRefresh: () => void; onPrevious: () => void; onNext: () => void;
  onOpen: (action: AccountAction, target?: AccountResponse | null) => void; onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function AccountActionDialog({ intent, userId, error, busy, onClose, onSubmit }: {
  intent: AccountIntent; userId: string; error: string; busy: boolean;
  onClose: () => void; onSubmit: AccountsProps["onSubmit"];
}) {
  const dialog = useRef<HTMLDialogElement | null>(null), form = useRef<HTMLFormElement | null>(null);
  const credentials = intent.action === "create" || intent.action === "reset";
  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
    return () => { form.current?.reset(); node?.close(); };
  }, []);
  return <dialog ref={dialog} className="ws-account-dialog" aria-labelledby="account-dialog-title" aria-describedby="account-dialog-impact"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form ref={form} onSubmit={onSubmit} autoComplete="off">
      <p className="ws-eyebrow">确认账号操作</p><h2 id="account-dialog-title">{accountActionLabel[intent.action]}</h2>
      {intent.target && <p className="ws-account-target"><strong>{intent.target.username}</strong><small>ID {intent.target.user_id}</small></p>}
      <p id="account-dialog-impact">{accountImpact(intent, userId)}</p>
      {intent.action === "create" && <>
        <label htmlFor="account-username">账号 <small>1—64位：英文字母、数字、下划线、点、连字符</small></label>
        <input id="account-username" name="username" autoComplete="off" required maxLength={64} pattern="[A-Za-z0-9_.\-]+" disabled={busy} autoFocus/>
        <label htmlFor="account-role">角色</label><select id="account-role" name="role" defaultValue="user" disabled={busy}><option value="user">普通用户</option><option value="admin">管理员</option></select>
        <p className="ws-account-help">管理员可以管理账号。请核对角色后提交。</p>
      </>}
      {credentials && <>
        <label htmlFor="account-password">{intent.action === "create" ? "初始密码" : "新临时密码"} <small>12—128个字符</small></label>
        <input id="account-password" name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy} autoFocus={intent.action === "reset"}/>
        <label htmlFor="account-confirm-password">再次输入密码</label>
        <input id="account-confirm-password" name="confirm_password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy}/>
      </>}
      <label className="ws-account-confirm"><input name="confirmed" type="checkbox" value="yes" required disabled={busy}/><span>我已核对账号和操作影响，确认执行。</span></label>
      {error && <p role="alert" className="ws-task-warning">{error}</p>}
      {busy && <p role="status">正在提交，请勿重复操作。离开页面只会停止等待，已发送的操作可能仍会完成。</p>}
      <div className="ws-account-dialog-actions"><button type="button" onClick={onClose} disabled={busy} autoFocus={!credentials}>取消</button>
        <button type="submit" className={intent.action === "disable" ? "ws-account-danger" : ""} disabled={busy}>{busy ? "提交中…" : `确认${accountActionLabel[intent.action]}`}</button></div>
    </form>
  </dialog>;
}

export function AccountsPanel(props: AccountsProps) {
  const heading = useRef<HTMLHeadingElement | null>(null), hadDialog = useRef(false);
  useEffect(() => {
    if (hadDialog.current && !props.intent) heading.current?.focus();
    hadDialog.current = props.intent !== null;
  }, [props.intent]);
  return <main className="ws-accounts-main" aria-labelledby="accounts-heading">
    <div className="ws-accounts-content"><header className="ws-accounts-heading"><div><p className="ws-eyebrow">账号与访问</p><h1 ref={heading} id="accounts-heading" tabIndex={-1}>用户管理</h1><p>管理账号登录与会话。文档仍按原授权范围访问。</p></div>
      <button type="button" onClick={() => props.onOpen("create")} disabled={props.actionBusy}>＋ 创建账号</button></header>
      <div className="ws-accounts-toolbar"><p>每页10个账号 · 状态以服务器为准</p><button type="button" onClick={props.onRefresh} disabled={props.actionBusy || props.listBusy}>刷新列表</button></div>
      {props.notice && <p className="ws-account-notice" role="status" aria-live="polite">{props.notice}</p>}
      {props.listError && <p className="ws-task-warning" role="alert">{props.listError}</p>}
      {props.listBusy && <p role="status" className="ws-account-help"><span className="spinner"/>正在读取账号列表…</p>}
      {props.accounts && !props.accounts.items.length && <p role="status">当前没有账号，请刷新列表确认。</p>}
      <section className="ws-account-cards" aria-label="账号列表" aria-busy={props.listBusy}>{props.accounts?.items.map(account => <article className="ws-account-card" key={account.user_id}>
        <div className="ws-account-card-heading"><h2>{account.username}{account.user_id === props.userId && <span>当前账号</span>}</h2><span className={`ws-account-badge ${account.active ? "" : "is-disabled"}`}>{account.active ? "已启用" : "已停用"}</span></div>
        <p className="ws-account-role">{account.role === "admin" ? "管理员" : "普通用户"} · {account.must_change_password ? "下次登录需改密" : "已完成首改"}</p>
        <p className="ws-account-id">ID {account.user_id}</p><p className="ws-account-help">创建：{account.created_at}<br/>更新：{account.updated_at}</p>
        <div className="ws-account-actions"><button type="button" onClick={() => props.onOpen(account.active ? "disable" : "enable", account)} disabled={props.actionBusy || props.listBusy}>{account.active ? "停用账号" : "启用账号"}</button>
          <button type="button" onClick={() => props.onOpen("reset", account)} disabled={props.actionBusy || props.listBusy}>重置密码</button>
          <button type="button" onClick={() => props.onOpen("revoke", account)} disabled={props.actionBusy || props.listBusy}>撤销全部会话</button></div>
      </article>)}</section>
      <nav className="ws-account-pagination" aria-label="账号分页"><button type="button" onClick={props.onPrevious} disabled={props.offset === 0 || props.listBusy || props.actionBusy}>上一页</button><span>第 {Math.floor(props.offset/10)+1} 页</span><button type="button" onClick={props.onNext} disabled={props.accounts?.next_offset == null || props.listBusy || props.actionBusy}>下一页</button></nav>
      <p className="ws-account-help">最后一个启用的管理员不能停用。重置密码或撤销会话后，已交付给浏览器的内容无法远程收回；后续访问会重新验证。</p>
    </div>
    {props.intent && <AccountActionDialog key={props.dialogKey} intent={props.intent} userId={props.userId} error={props.dialogError} busy={props.actionBusy} onClose={props.onClose} onSubmit={props.onSubmit}/>}
  </main>;
}
