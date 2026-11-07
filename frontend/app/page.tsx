"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { setCsrfToken } from "@/lib/api/client";
import { ApiError, AuthService, DocumentsService, SearchService } from "@/lib/api/generated";
import type { DocumentListItem, DocumentListResponse, MeResponse, SearchHit, SearchResponse } from "@/lib/api/generated";
import { RequestGeneration, privatePreviewPath } from "@/lib/workspace-lifecycle";
import { matchesSearchTarget, searchDocumentId } from "@/lib/document-selection";
import type { SearchMode } from "@/lib/document-selection";
import { WorkspaceShell } from "@/components/workspace/workspace";
import "./workspace.css";
import { useUploadTasks } from "@/lib/use-upload-tasks";

type Mode = "checking" | "login" | "password" | "workspace" | "unavailable";
type Cancelable<T> = PromiseLike<T> & { cancel(): void };

export default function Home() {
  const [mode, setMode] = useState<Mode>("checking");
  const [me, setMe] = useState<MeResponse | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<SearchHit | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("library");
  const [targetDocument, setTargetDocument] = useState<DocumentListItem | null>(null);
  const targetRef = useRef<DocumentListItem | null>(null);
  const [documentName, setDocumentName] = useState("");
  const [documentList, setDocumentList] = useState<DocumentListResponse | null>(null);
  const [listBusy, setListBusy] = useState(false);
  const [listError, setListError] = useState("");
  const [listCursors, setListCursors] = useState<(string | null)[]>([null]);
  const [listRefresh, setListRefresh] = useState(0);
  const listGeneration = useRef(new RequestGeneration());
  const listScope = useRef<string | null>(null);
  const generation = useRef(new RequestGeneration());
  const imageRequest = useRef<AbortController | null>(null);
  const imageObject = useRef<string | null>(null);
  const imageSequence = useRef(0);
  const identity = useRef<string | null>(null);
  const channel = useRef<BroadcastChannel | null>(null);
  const form = useRef<HTMLFormElement | null>(null);
  const [workspaceView, setWorkspaceView] = useState<"search" | "tasks">("search");
  const [leavingWorkspace, setLeavingWorkspace] = useState(false);
  const taskWorkspace = useUploadTasks({
    enabled: mode === "workspace" && !leavingWorkspace, userId: me?.user_id ?? null, csrfToken: me?.csrf_token,
    onSessionError: error => businessError(error),
    onChanged: () => invalidateDocumentScope("入库任务已更新，请刷新范围或重新选择就绪文档。"),
    onBrowse: job => {
      clearResults(); clearDocuments(); setSearchMode("document"); setDocumentName(job.display_name);
      setWorkspaceView("search"); setNotice("请选择已完成文档，再提交内容问题。");
    },
  });
  const resetTasks = taskWorkspace.reset;

  const clearImage = useCallback(() => {
    imageSequence.current += 1; imageRequest.current?.abort(); imageRequest.current = null;
    if (imageObject.current) URL.revokeObjectURL(imageObject.current);
    imageObject.current = null; setImage(null); setImageBusy(false); setImageError("");
  }, []);
  const clearResults = useCallback(() => {
    generation.current.reset(); clearImage(); setResult(null); setSelected(null); setSubmittedQuestion(""); setBusy(false);
  }, [clearImage]);
  const clearDocuments = useCallback(() => {
    listGeneration.current.reset(); listScope.current = null; targetRef.current = null;
    setSearchMode("library"); setTargetDocument(null); setDocumentName(""); setDocumentList(null);
    setListBusy(false); setListError(""); setListCursors([null]);
  }, []);
  const lock = useCallback((next: Mode = "login", message = "") => {
    clearResults(); clearDocuments(); resetTasks(); setWorkspaceView("search"); setLeavingWorkspace(false); setCsrfToken(); identity.current = null;
    setMe(null); setQuestion(""); setMode(next); setNotice(message); form.current?.reset();
  }, [clearResults, clearDocuments, resetTasks]);
  const announce = useCallback(() => { channel.current?.postMessage("session-changed"); }, []);
  async function tracked<T>(request: Cancelable<T>) {
    const release = generation.current.track(() => request.cancel());
    try { return await request; } finally { release(); }
  }
  const restore = useCallback(async () => {
    lock("checking");
    const stamp = generation.current.current();
    try {
      const current = await tracked(AuthService.getMe());
      if (!generation.current.accepts(stamp) || document.visibilityState === "hidden") return;
      identity.current = current.user_id; setMe(current); setCsrfToken(current.csrf_token);
      setMode(current.must_change_password ? "password" : "workspace");
    } catch (error) {
      if (!generation.current.accepts(stamp)) return;
      if (error instanceof ApiError && error.status === 401) lock("login");
      else lock("unavailable", "暂时无法确认登录状态，请稍后重试。");
    }
  }, [lock]);

  useEffect(() => {
    channel.current = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("layoutpatch-session") : null;
    if (channel.current) channel.current.onmessage = () => { void restore(); };
    const visibility = () => { if (document.visibilityState === "hidden") lock("checking"); else void restore(); };
    const pagehide = () => lock("checking");
    const pageshow = (event: PageTransitionEvent) => { if (event.persisted) void restore(); };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", pagehide); window.addEventListener("pageshow", pageshow);
    void restore();
    return () => {
      generation.current.reset(); listGeneration.current.reset(); clearImage(); setCsrfToken(); channel.current?.close(); channel.current = null;
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", pagehide); window.removeEventListener("pageshow", pageshow);
    };
  }, [restore, lock, clearImage]);

  useEffect(() => {
    if (!me || mode === "checking") return;
    const timer = window.setInterval(async () => {
      const stamp = generation.current.current();
      try {
        const current = await tracked(AuthService.getMe());
        if (!generation.current.accepts(stamp)) return;
        if (current.user_id !== identity.current || current.csrf_token !== me.csrf_token || current.must_change_password !== me.must_change_password) void restore();
      } catch (error) {
        if (!generation.current.accepts(stamp)) return;
        if (error instanceof ApiError && error.status === 401) lock("login", "登录已失效，请重新登录。");
        else lock("unavailable", "连接中断，已隐藏当前结果。请重新连接。");
      }
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [me, mode, lock, restore]);

  function businessError(error: unknown) {
    if (error instanceof ApiError) {
      const detail = (error.body as { detail?: string } | undefined)?.detail;
      if (error.status === 401) { lock("login", "登录已失效，请重新登录。"); announce(); return; }
      if (error.status === 403 && detail === "PASSWORD_CHANGE_REQUIRED") {
        clearResults(); clearDocuments(); resetTasks(); setMode("password"); setNotice("请先设置新密码，再继续检索。"); return;
      }
      if (error.status === 404 || error.status === 409) { invalidateDocumentScope(); return; }
      if (error.status === 503) { setNotice(detail === "MODEL_BUSY" ? "检索服务繁忙，请稍后重试。" : "检索服务暂时不可用，请稍后重试。"); return; }
      if (error.status === 422) { setNotice("请检查问题长度和返回页数。"); return; }
    }
    setNotice("连接暂时中断，请稍后重试。");
  }
  function invalidateDocumentScope(message = searchMode === "document" ? "文档或访问范围已变化，请重新选择文档后检索。" : "可访问的文档已变化，请重新检索。") {
    clearResults(); targetRef.current = null; setTargetDocument(null);
    listGeneration.current.reset(); setDocumentList(null); setListCursors([null]); setListRefresh(value => value + 1);
    setNotice(message);
  }
  useEffect(() => {
    if (mode !== "workspace" || !me || searchMode !== "document") return;
    const stamp = listGeneration.current.reset();
    setDocumentList(null); setListError(""); setListBusy(true);
    const timer = window.setTimeout(async () => {
      const request = DocumentsService.listDocuments(documentName, 10, listCursors[listCursors.length - 1]);
      const release = listGeneration.current.track(() => request.cancel());
      try {
        const response = await request;
        if (!listGeneration.current.accepts(stamp)) return;
        if (targetRef.current && listScope.current && listScope.current !== response.scope_version) {
          clearResults(); targetRef.current = null; setTargetDocument(null);
          setNotice("文档列表已变化，请重新选择文档。");
        }
        const updated = response.items.find(item => item.document_id === targetRef.current?.document_id);
        if (updated && !updated.searchable) {
          clearResults(); targetRef.current = null; setTargetDocument(null); setNotice("所选文档暂不可检索，请重新选择。");
        } else if (updated) { targetRef.current = updated; setTargetDocument(updated); }
        listScope.current = response.scope_version; setDocumentList(response);
      } catch (error) {
        if (!listGeneration.current.accepts(stamp)) return;
        clearResults(); targetRef.current = null; setTargetDocument(null); setDocumentList(null);
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) { businessError(error); return; }
        const message = error instanceof ApiError && (error.status === 409 || error.status === 422)
          ? "文档列表或分页已变化，请刷新列表。" : "文档列表暂时无法加载，请刷新列表。";
        setListError(message); setNotice(message);
      } finally { release(); if (listGeneration.current.accepts(stamp)) setListBusy(false); }
    }, documentName ? 300 : 0);
    return () => { window.clearTimeout(timer); listGeneration.current.reset(); };
    // Private list requests have their own generation: typing cannot cancel a content query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, me?.user_id, searchMode, documentName, listCursors, listRefresh, clearResults]);

  function changeSearchMode(next: SearchMode) {
    if (next === searchMode) return;
    clearResults(); clearDocuments(); setSearchMode(next); setNotice("");
  }
  function chooseDocument(document: DocumentListItem) {
    if (!document.searchable) return;
    if (document.document_id !== targetRef.current?.document_id || document.document_version_id !== targetRef.current.document_version_id) clearResults();
    targetRef.current = document; setTargetDocument(document); setNotice("");
  }
  function changeDocumentName(value: string) {
    // The server snapshot is specific to the normalized filename filter.
    listGeneration.current.reset(); listScope.current = null;
    setNotice(current => current === listError ? "" : current);
    setDocumentName(value); setDocumentList(null); setListError(""); setListCursors([null]);
  }
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const username = String(data.get("username") ?? "").trim(), password = String(data.get("password") ?? "");
    event.currentTarget.reset(); lock("login"); setBusy(true); announce();
    const stamp = generation.current.current();
    try {
      const current = await tracked(AuthService.login({ username, password }));
      if (!generation.current.accepts(stamp)) return;
      identity.current = current.user_id; setMe(current); setCsrfToken(current.csrf_token);
      setMode(current.must_change_password ? "password" : "workspace"); announce();
    } catch (error) {
      if (!generation.current.accepts(stamp)) return;
      setNotice(error instanceof ApiError && error.status === 401 ? "账号或密码不正确，请重试。" :
        error instanceof ApiError && error.status === 429 ? "尝试次数较多，请五分钟后重试。" : "登录服务暂时不可用，请稍后重试。");
    } finally { if (generation.current.accepts(stamp)) setBusy(false); }
  }
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const current_password = String(data.get("current_password") ?? ""), new_password = String(data.get("new_password") ?? "");
    if (new_password !== String(data.get("confirm_password") ?? "")) { setNotice("两次输入的新密码不一致。"); return; }
    if (new_password === current_password) { setNotice("新密码需要与当前密码不同。"); return; }
    event.currentTarget.reset(); clearResults(); setBusy(true); setNotice("");
    const stamp = generation.current.current();
    try {
      await tracked(AuthService.changePassword({ current_password, new_password }));
      if (!generation.current.accepts(stamp)) return;
      lock("login", "密码已更新，请使用新密码重新登录。"); announce();
    } catch (error) {
      if (!generation.current.accepts(stamp)) return;
      if (error instanceof ApiError && error.status === 400) setNotice("当前密码不正确，请重新输入。");
      else businessError(error);
    } finally { if (generation.current.accepts(stamp)) setBusy(false); }
  }
  async function logout() {
    const csrf = me?.csrf_token;
    setLeavingWorkspace(true); clearResults(); clearDocuments(); resetTasks(); setQuestion(""); setNotice(""); setBusy(true);
    const stamp = generation.current.current();
    try {
      setCsrfToken(csrf); await tracked(AuthService.logout());
      if (generation.current.accepts(stamp)) { lock("login", "已安全退出，可以切换账号。"); announce(); }
    } catch (error) {
      if (!generation.current.accepts(stamp)) return;
      if (error instanceof ApiError && error.status === 401) { lock("login", "已退出登录。"); announce(); }
      else lock("unavailable", "退出尚未确认，已隐藏当前内容。请重新连接后重试退出。");
    }
  }
  async function preview(hit: SearchHit, stamp = generation.current.current()) {
    clearImage(); setSelected(hit); setImageBusy(true);
    const sequence = imageSequence.current, controller = new AbortController(); imageRequest.current = controller;
    try {
      const response = await fetch(privatePreviewPath(hit.preview_url), {
        credentials: "same-origin", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer", signal: controller.signal,
      });
      if (!generation.current.accepts(stamp) || sequence !== imageSequence.current) return;
      if (response.status === 401) { lock("login", "登录已失效，请重新登录。"); announce(); return; }
      if (response.status === 403) { clearResults(); clearDocuments(); resetTasks(); setMode("password"); setNotice("请先设置新密码。"); return; }
      if (response.status === 404) { invalidateDocumentScope("页面访问权限已变化，请重新检索。"); return; }
      if (!response.ok || response.headers.get("content-type")?.split(";", 1)[0] !== "image/png") throw new Error("Preview unavailable");
      const blob = await response.blob();
      if (!generation.current.accepts(stamp) || sequence !== imageSequence.current) return;
      const url = URL.createObjectURL(blob); imageObject.current = url; setImage(url);
    } catch {
      if (!controller.signal.aborted && generation.current.accepts(stamp) && sequence === imageSequence.current) setImageError("暂时无法加载页面，请重试。");
    } finally { if (generation.current.accepts(stamp) && sequence === imageSequence.current) setImageBusy(false); }
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const q = question.trim(), k = Number(data.get("k"));
    if (!q || q.length > 2000 || !Number.isInteger(k) || k < 1 || k > 50) { setNotice("请检查问题长度和返回页数。"); return; }
    const target = targetRef.current;
    let documentId: string | undefined;
    try { documentId = searchDocumentId(searchMode, target); }
    catch { setNotice("请先选择一份已就绪的文档，再检索内容。"); return; }
    clearResults(); setSubmittedQuestion(q); setNotice(""); setBusy(true); const stamp = generation.current.current();
    try {
      const response = await tracked(SearchService.searchPages(q, k, documentId));
      if (!generation.current.accepts(stamp)) return;
      if (!matchesSearchTarget(response, searchMode, target)) { clearResults(); setNotice("返回的检索范围不一致，请重新选择后检索。"); return; }
      setResult(response); if (response.items[0]) void preview(response.items[0], stamp);
    } catch (error) { if (generation.current.accepts(stamp)) businessError(error); }
    finally { if (generation.current.accepts(stamp)) setBusy(false); }
  }

  if (mode === "workspace" && me) return <WorkspaceShell
    view={workspaceView} onViewChange={setWorkspaceView} taskPanel={taskWorkspace.panel}
    username={me.username} role={me.role} question={question} submittedQuestion={submittedQuestion}
    busy={busy} notice={notice} result={result} selected={selected}
    image={image} imageBusy={imageBusy} imageError={imageError}
    searchMode={searchMode} targetDocument={targetDocument} onModeChange={changeSearchMode}
    documentPicker={{ name: documentName, response: documentList, busy: listBusy, error: listError, selected: targetDocument, page: listCursors.length,
      onNameChange: changeDocumentName, onSelect: chooseDocument,
      onPrevious: () => { listGeneration.current.reset(); setListCursors(value => value.slice(0, -1)); },
      onNext: () => { if (documentList?.next_cursor) { listGeneration.current.reset(); setListCursors(value => [...value, documentList.next_cursor]); } },
      onRefresh: () => { listGeneration.current.reset(); setNotice(current => current === listError ? "" : current); setListCursors([null]); setListRefresh(value => value + 1); },
    }}
    onQuestionChange={setQuestion} onSearch={search} onSelect={hit => void preview(hit)}
    onNewSearch={() => { clearResults(); setWorkspaceView("search"); setQuestion(""); setNotice(""); }}
    onLogout={() => void logout()}
  />;

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="LayoutPatch 首页"><span className="brand-mark" aria-hidden="true">L<span>·</span></span>LayoutPatch<span className="brand-caption">视觉文档检索</span></a>
      {me && <div className="account"><span className="avatar" aria-hidden="true">{me.username.slice(0, 1).toUpperCase()}</span><span>{me.username}<small>{me.role === "admin" ? "管理员" : "个人空间"}</small></span><button className="button-quiet" onClick={() => void logout()} disabled={busy && mode !== "workspace"}>退出 / 换号</button></div>}
    </header><main>
      {mode === "checking" && <div className="center-state" role="status"><span className="spinner"/>正在确认登录状态…</div>}
      {mode === "unavailable" && <section className="reconnect"><p className="eyebrow">连接状态</p><h1>暂时无法连接</h1><p role="alert">{notice}</p><button onClick={() => void restore()}>重新连接</button></section>}
      {mode === "login" && <div className="auth-layout"><section className="welcome"><p className="eyebrow">从问题，找到页面</p><h1>让文档里的线索，<br/>回到眼前。</h1><p className="lead">用自然语言提问，找到相关页面，<br/>再回到原文查看上下文。</p><div className="paper-scene" aria-hidden="true"><div className="paper paper-back"/><div className="paper paper-front"><span className="paper-label">DOCUMENT / 01</span><i/><i/><i className="short"/><div className="paper-figure"><span/><span/><span/></div><i/><i/><i className="short"/></div><span className="scene-note">阅读 · 检索 · 核对</span></div><p className="privacy-note"><span aria-hidden="true">◈</span> 你的私有文档，仅在授权范围内检索。</p></section>
        <section className="auth-card"><p className="eyebrow">欢迎回来</p><h2>登录你的工作空间</h2><p className="muted">使用管理员分配的账号。首次登录后需设置新密码。</p><form ref={form} onSubmit={login}>
          <label htmlFor="username">账号</label><input id="username" name="username" autoComplete="username" required maxLength={64} placeholder="请输入账号" disabled={busy}/>
          <label htmlFor="password">密码</label><input id="password" name="password" type="password" autoComplete="current-password" required maxLength={128} placeholder="请输入密码" disabled={busy}/>
          {notice && <p className="notice" role="alert">{notice}</p>}<button className="full" disabled={busy}>{busy ? "登录中…" : "登录工作空间"}<span aria-hidden="true"> →</span></button>
        </form><p className="form-footnote">忘记密码？请联系管理员重置。</p></section></div>}
      {mode === "password" && <section className="password-card auth-card"><p className="eyebrow">保护你的账号</p><h1>设置新密码</h1><p className="muted">首次使用前，请替换初始密码。更新后需要重新登录。</p><form ref={form} onSubmit={changePassword}>
        <label htmlFor="current_password">当前密码</label><input id="current_password" name="current_password" type="password" autoComplete="current-password" required maxLength={128} disabled={busy}/>
        <label htmlFor="new_password">新密码 <span className="field-hint">12–128 个字符</span></label><input id="new_password" name="new_password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy}/>
        <label htmlFor="confirm_password">再次输入新密码</label><input id="confirm_password" name="confirm_password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} disabled={busy}/>
        {notice && <p className="notice" role="alert">{notice}</p>}<button className="full" disabled={busy}>{busy ? "更新中…" : "更新密码并重新登录"}</button>
      </form></section>}

    </main><footer className="site-footer"><span>LayoutPatch</span><span>让问题与文档相遇</span></footer>
  </div>;
}
