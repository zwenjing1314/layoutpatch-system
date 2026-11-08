"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { AdminService, ApiError } from "@/lib/api/generated";
import type { AccountList, AccountMutation } from "@/lib/api/generated";
import type { AccountsProps } from "@/components/workspace/accounts";
import { accountActionLabel, accountFailure } from "@/lib/account-state";
import type { AccountAction, AccountIntent } from "@/lib/account-state";
import { RequestGeneration } from "@/lib/workspace-lifecycle";
import { boundedTaskRequest } from "@/lib/task-state";

type Options = {
  enabled: boolean; userId: string | null; csrfToken?: string;
  onSessionError: (error: unknown) => void;
  onSelfChanged: (action: AccountAction, uncertain: boolean) => void;
};

export function useAccounts(options: Options) {
  const current = useRef(options); current.current = options;
  const listGeneration = useRef(new RequestGeneration()), actionGeneration = useRef(new RequestGeneration());
  const inFlight = useRef(false);
  const [accounts, setAccounts] = useState<AccountList | null>(null), [listBusy, setListBusy] = useState(false);
  const [listError, setListError] = useState(""), [notice, setNotice] = useState("");
  const [offset, setOffset] = useState(0), [refresh, setRefresh] = useState(0);
  const [intent, setIntent] = useState<AccountIntent | null>(null), [dialogKey, setDialogKey] = useState(0);
  const [actionBusy, setActionBusy] = useState(false), [dialogError, setDialogError] = useState("");

  const reset = useCallback(() => {
    listGeneration.current.reset(); actionGeneration.current.reset(); inFlight.current = false;
    setAccounts(null); setListBusy(false); setListError(""); setNotice(""); setOffset(0);
    setIntent(null); setDialogKey(v => v+1); setActionBusy(false); setDialogError("");
  }, []);
  const reload = useCallback((first = false) => {
    listGeneration.current.reset(); setAccounts(null); setListError("");
    if (first) setOffset(0);
    setRefresh(v => v+1);
  }, []);
  function sessionError(error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      reset(); current.current.onSessionError(error); return true;
    }
    return false;
  }
  useEffect(() => {
    reset();
    return () => { listGeneration.current.reset(); actionGeneration.current.reset(); inFlight.current = false; };
  }, [options.enabled, options.userId, reset]);

  useEffect(() => {
    if (!options.enabled || !options.userId) return;
    const stamp = listGeneration.current.reset(); setAccounts(null); setListBusy(true); setListError("");
    async function load() {
      try {
        const response = await boundedTaskRequest(AdminService.listAccounts(10, offset), listGeneration.current, 15_000);
        if (!listGeneration.current.accepts(stamp) || !current.current.enabled) return;
        // A concurrent account update can move offset pages; never render a false empty last page.
        if (offset > 0 && !response.items.length) { setOffset(0); return; }
        setAccounts(response);
      } catch (error) {
        if (!listGeneration.current.accepts(stamp) || !current.current.enabled || sessionError(error)) return;
        setListError("账号列表暂时无法确认，请刷新列表。");
      } finally { if (listGeneration.current.accepts(stamp)) setListBusy(false); }
    }
    void load();
    return () => { listGeneration.current.reset(); };
    // Callbacks read current refs; account requests never cancel retrieval requests.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.enabled, options.userId, offset, refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || !intent || !current.current.enabled || !current.current.csrfToken) return;
    const form = event.currentTarget, data = new FormData(form), captured = intent;
    const password = String(data.get("password") ?? ""), confirm = String(data.get("confirm_password") ?? "");
    // Secrets stay only in this request closure and DOM inputs, never in React state/storage.
    form.querySelectorAll<HTMLInputElement>('input[type="password"]').forEach(input => { input.value = ""; });
    if (data.get("confirmed") !== "yes") { setDialogError("请先确认操作影响。"); return; }
    if (["create", "reset"].includes(captured.action) && (password.length < 12 || password.length > 128 || password !== confirm)) {
      setDialogError("两次密码需一致，长度为12—128个字符，请重新输入。"); return;
    }
    const username = String(data.get("username") ?? "").trim(), role = String(data.get("role") ?? "user");
    if (captured.action === "create" && (!/^[A-Za-z0-9_.-]{1,64}$/.test(username) || !["admin", "user"].includes(role))) {
      setDialogError("账号需为1—64个英文字母、数字、下划线、点或连字符。"); return;
    }
    const self = captured.target?.user_id === current.current.userId;
    inFlight.current = true; setActionBusy(true); setDialogError(""); setNotice("");
    listGeneration.current.reset(); setListBusy(false);
    const stamp = actionGeneration.current.reset();
    try {
      const id = captured.target?.user_id ?? "";
      const request = captured.action === "create" ? AdminService.createAccount({ username, password, role: role as "admin" | "user" })
        : captured.action === "reset" ? AdminService.resetAccountPassword(id, { password })
        : captured.action === "revoke" ? AdminService.revokeAccountSessions(id, {})
        : AdminService.setAccountActive(id, { active: captured.action === "enable" });
      const response: AccountMutation = await boundedTaskRequest(request, actionGeneration.current, 15_000);
      if (!actionGeneration.current.accepts(stamp) || !current.current.enabled) return;
      setIntent(null); setDialogKey(v => v+1);
      if (self && response.changed && captured.action !== "enable") {
        reset(); current.current.onSelfChanged(captured.action, false); return;
      }
      setNotice(response.changed ? `${accountActionLabel[captured.action]}成功。${captured.action === "create" || captured.action === "reset" ? "新密码仅由你本次输入，不会再次显示；使用者下次登录必须改密。" : ""}` : "账号已处于所选状态，未重复撤销会话。");
      reload(captured.action === "create");
    } catch (error) {
      if (!actionGeneration.current.accepts(stamp) || !current.current.enabled || sessionError(error)) return;
      setIntent(null); setDialogKey(v => v+1);
      const uncertain = !(error instanceof ApiError) || error.status >= 500;
      if (self && uncertain) { reset(); current.current.onSelfChanged(captured.action, true); return; }
      setNotice(accountFailure(error instanceof ApiError ? error : null));
      // Never retry a write. Reading the current list is safe even when the write outcome is uncertain.
      reload();
    } finally {
      if (actionGeneration.current.accepts(stamp)) { inFlight.current = false; setActionBusy(false); }
    }
  }

  const panel: AccountsProps = {
    userId: options.userId ?? "", accounts, listBusy, listError, notice, offset, intent, dialogKey, dialogError, actionBusy,
    onRefresh() { if (!inFlight.current) reload(); },
    onPrevious() { if (!inFlight.current && !listBusy && offset > 0) { listGeneration.current.reset(); setAccounts(null); setOffset(v => Math.max(0,v-10)); } },
    onNext() { if (!inFlight.current && !listBusy && accounts?.next_offset != null) { listGeneration.current.reset(); setAccounts(null); setOffset(accounts.next_offset); } },
    onOpen(action, target = null) {
      if (inFlight.current || !current.current.enabled) return;
      setDialogError(""); setNotice(""); setDialogKey(v => v+1); setIntent({ action, target });
    },
    onClose() { if (!inFlight.current) { setIntent(null); setDialogError(""); setDialogKey(v => v+1); } },
    onSubmit: submit,
  };
  return { panel, reset };
}
