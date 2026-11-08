"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, RefObject } from "react";
import type { DocumentListItem, HistoryDetail, SearchHit, SearchResponse } from "@/lib/api/generated";
import type { SearchMode } from "@/lib/document-selection";
import { DocumentPicker, ScopeSwitch } from "./document-picker";
import type { DocumentPickerProps } from "./document-picker";
import { UploadTasksPanel } from "./upload-tasks";
import type { UploadTasksProps } from "./upload-tasks";
import { RegionCanvas, RegionControls } from './region-evidence';
import type { RegionsProps } from '@/lib/use-regions';
import { AccountsPanel } from './accounts';
import type { AccountsProps } from './accounts';
import { SharingPanel } from './sharing';
import { DeletionPanel } from './deletion';
import type { DeletionProps } from '@/lib/use-deletion';
import type { SharingProps } from '@/lib/use-sharing';
import type { HistoryProps } from '@/lib/use-history';
import { IndexesPanel } from './indexes';
import type { IndexesProps } from '@/lib/use-indexes';
import { AuditPanel } from './audit';
import type { AuditProps } from '@/lib/use-audit';
import { HistoryBanner, HistorySidebar } from './history';
import { ThemeToggle } from '../theme-toggle';

type WorkspaceProps = {
  view: "search" | "tasks" | "accounts" | "sharing" | "deletion" | "audit" | "indexes";
  onViewChange: (view: "search" | "tasks" | "accounts" | "sharing" | "deletion" | "audit" | "indexes") => void;
  taskPanel: UploadTasksProps;
  accountPanel?: AccountsProps;
  sharingPanel?: SharingProps;
  deletionPanel?: DeletionProps;
  auditPanel?: AuditProps;
  indexPanel?: IndexesProps;
  historyPanel?: HistoryProps;
  historyDetail?: HistoryDetail | null;
  queryK?: number;
  onKChange?: (value:number) => void;
  restoredTarget?: {id:string|null;available:boolean}|null;
  searchPending?: boolean;
  searchNotice?: string;
  onVerifySearch?: () => void;
  onDismissSearch?: () => void;
  onRepeatHistory?: () => void;
  username: string;
  role: string;
  question: string;
  submittedQuestion: string;
  busy: boolean;
  notice: string;
  result: SearchResponse | null;
  selected: SearchHit | null;
  image: string | null;
  imageBusy: boolean;
  imageError: string;
  regions?: RegionsProps;
  searchMode: SearchMode;
  targetDocument: DocumentListItem | null;
  documentPicker: DocumentPickerProps;
  onModeChange: (mode: SearchMode) => void;
  onQuestionChange: (value: string) => void;
  onSearch: (event: FormEvent<HTMLFormElement>) => void;
  onSelect: (hit: SearchHit) => void;
  onNewSearch: () => void;
  onLogout: () => void;
};

export function WorkspaceSidebar({ username, role, collapsed, newSearchRef, onToggle, onNewSearch, onLogout, view, onViewChange, historyPanel, historyVisible, onToggleHistory }: {
  username: string; role: WorkspaceProps["role"]; collapsed: boolean;
  newSearchRef: RefObject<HTMLButtonElement | null>;
  onToggle: () => void; onNewSearch: () => void; onLogout: () => void;
  view: WorkspaceProps["view"]; onViewChange: WorkspaceProps["onViewChange"];
  historyPanel?: HistoryProps; historyVisible?:boolean; onToggleHistory?:()=>void;
}) {
  return <aside className="ws-sidebar" id="workspace-navigation" aria-label="工作台导航">
    <div className="ws-brand-row"><a href="/" className="ws-brand" aria-label="LayoutPatch 首页"><span className="ws-mark" aria-hidden="true">L<span>·</span></span><span className="ws-sidebar-text">LayoutPatch</span></a>
      <button type="button" className="ws-icon-button ws-collapse" onClick={onToggle} aria-label={collapsed ? "展开侧栏" : "折叠侧栏"} aria-expanded={!collapsed} title={collapsed ? "展开侧栏" : "折叠侧栏"}>{collapsed ? "›" : "‹"}</button></div>
    <button type="button" ref={newSearchRef} className="ws-new-search" onClick={onNewSearch} title="新检索"><span aria-hidden="true">＋</span><span className="ws-sidebar-text">新检索</span><span className="sr-only ws-collapsed-label">新检索</span></button>
    <nav aria-label="当前功能"><button type="button" className="ws-current" aria-current={!view || view === "search" ? "page" : undefined} onClick={() => onViewChange("search")} title="文档检索"><span aria-hidden="true">▤</span><span className="ws-sidebar-text">文档检索</span><span className="sr-only ws-collapsed-label">文档检索</span></button>
      <button type="button" className="ws-current" aria-current={view === "tasks" ? "page" : undefined} onClick={() => onViewChange("tasks")} title="上传与任务"><span aria-hidden="true">⇧</span><span className="ws-sidebar-text">上传与任务</span><span className="sr-only ws-collapsed-label">上传与任务</span></button>
      <button type="button" className="ws-current" aria-current={view === "deletion" ? "page" : undefined} onClick={() => onViewChange("deletion")} title="删除与清理"><span aria-hidden="true">⌫</span><span className="ws-sidebar-text">删除与清理</span><span className="sr-only ws-collapsed-label">删除与清理</span></button>
      {historyPanel&&<button type="button" className="ws-current" aria-expanded={historyVisible&&!collapsed} aria-controls="history-heading" onClick={onToggleHistory} title="检索历史"><span aria-hidden="true">◷</span><span className="ws-sidebar-text">检索历史</span><span className="sr-only ws-collapsed-label">检索历史</span></button>}
      {role === "admin" && <><button type="button" className="ws-current" aria-current={view === "accounts" ? "page" : undefined} onClick={() => onViewChange("accounts")} title="用户管理"><span aria-hidden="true">♙</span><span className="ws-sidebar-text">用户管理</span><span className="sr-only ws-collapsed-label">用户管理</span></button><button type="button" className="ws-current" aria-current={view === "sharing" ? "page" : undefined} onClick={() => onViewChange("sharing")} title="共享管理"><span aria-hidden="true">⇄</span><span className="ws-sidebar-text">共享管理</span><span className="sr-only ws-collapsed-label">共享管理</span></button><button type="button" className="ws-current" aria-current={view === "audit" ? "page" : undefined} onClick={() => onViewChange("audit")} title="审计与任务"><span aria-hidden="true">≡</span><span className="ws-sidebar-text">审计与任务</span><span className="sr-only ws-collapsed-label">审计与任务</span></button><button type="button" className="ws-current" aria-current={view === "indexes" ? "page" : undefined} onClick={() => onViewChange("indexes")} title="配置身份与回退"><span aria-hidden="true">◇</span><span className="ws-sidebar-text">配置身份与回退</span><span className="sr-only ws-collapsed-label">配置身份与回退</span></button></>}</nav>
    {historyPanel&&<HistorySidebar {...historyPanel}/>}
    {!historyPanel&&<p className="ws-sidebar-note ws-sidebar-text">从问题找到页面，<br/>再回到原文核对。</p>}
    <div className="ws-account"><span className="ws-avatar" aria-hidden="true">{username.slice(0, 1).toUpperCase()}</span><div className="ws-sidebar-text"><strong>{username}</strong><small>{role === "admin" ? "管理员" : "个人空间"}</small></div>
      <button type="button" className="ws-logout" onClick={onLogout} title="退出 / 换号"><span aria-hidden="true">↪</span><span className="ws-sidebar-text">退出 / 换号</span><span className="sr-only ws-collapsed-label">退出 / 换号</span></button></div>
  </aside>;
}

export function QueryComposer({ question, busy, inputRef, onQuestionChange, onSearch, searchMode = "library", targetDocument = null, queryK=3, onKChange, restoredTarget, pending=false }: {
  question: string; busy: boolean; inputRef: RefObject<HTMLTextAreaElement | null>;
  searchMode?: SearchMode; targetDocument?: DocumentListItem | null;
  queryK?:number; onKChange?:(value:number)=>void; restoredTarget?:WorkspaceProps['restoredTarget']; pending?:boolean;
  onQuestionChange: WorkspaceProps["onQuestionChange"]; onSearch: WorkspaceProps["onSearch"];
}) {
  return <form className="ws-query" onSubmit={onSearch} aria-label={searchMode === "document" ? "单文档检索表单" : "文档库检索表单"}>
    <label className="sr-only" htmlFor="question">检索问题</label>
    <textarea ref={inputRef} id="question" name="q" value={question} onChange={event => onQuestionChange(event.target.value)} required maxLength={2000} placeholder="例如：文中如何比较硬件面积与能耗？" rows={3} aria-describedby="workspace-scope"/>
    <div className="ws-query-controls"><span id="workspace-scope">◈ {searchMode === "library" ? "个人与共享文档" : targetDocument ? `仅检索：${targetDocument.display_name} · ID ${targetDocument.document_id.slice(0, 8)}` : restoredTarget?.available&&restoredTarget.id ? `原单文档目标 ID ${restoredTarget.id.slice(0,8)}` : "请先选择一份已就绪的文档"}</span><label htmlFor="k">返回页数</label><select id="k" name="k" value={queryK} onChange={e=>onKChange?.(Number(e.target.value))}>{![3,5,10].includes(queryK)&&<option value={queryK}>{queryK} 页</option>}<option value="3">3 页</option><option value="5">5 页</option><option value="10">10 页</option></select><button type="submit" disabled={busy || pending || !question.trim() || searchMode === "document" && !targetDocument?.searchable && !(restoredTarget?.available&&restoredTarget.id)}>{pending&&!busy?'先核对提交':busy ? (question.trim() ? "检索中…" : "请稍候…") : "检索文档"}<span aria-hidden="true"> ↗</span></button></div>
  </form>;
}

export function RetrievalResults({ result, selected, onSelect, historical=false }: {
  result: SearchResponse; selected: SearchHit | null; onSelect: WorkspaceProps["onSelect"]; historical?:boolean;
}) {
  if (!result.items.length) return <section className="ws-empty" role="status"><span aria-hidden="true">▤</span><h2>{historical?'这条历史暂无可用的页面引用':'当前范围没有可检索页面'}</h2><p>{historical?'原检索可能为空，或原引用已经失效。没有自动重新检索，也不会恢复失效内容。':result.search_mode === "document" ? "请刷新文档列表，核对所选文档状态后重试。" : "你的空间中还没有可用页面，也暂无共享文档。请联系管理员。"}</p></section>;
  return <section className="ws-results" aria-label="检索结果"><div className="ws-result-heading"><h2>相关页面 <span>{result.items.length}</span></h2><p>{historical?'原检索分数与排名 · 仅当前授权引用，排名可能不连续':'按相关分数排序 · 请结合原文核对'}</p></div>
    <div className="ws-result-list">{result.items.map(hit => <button type="button" key={hit.page_id} className={`ws-result-card ${selected?.page_id === hit.page_id ? "is-selected" : ""}`} aria-pressed={selected?.page_id === hit.page_id} onClick={() => onSelect(hit)}>
      <span className="ws-rank">{String(hit.page_rank).padStart(2, "0")}</span><span className="ws-result-copy"><strong>{hit.document_name}</strong><span>第 {hit.page_number} 页 · 相关分数 {hit.page_score.toFixed(2)}</span><small>查看页面原文 <span aria-hidden="true">↗</span></small></span><span className="ws-selection" aria-hidden="true">{selected?.page_id === hit.page_id ? "已选" : ""}</span>
    </button>)}</div></section>;
}

export function EvidencePanel({ selected, image, imageBusy, imageError, headingRef, onRetry, regions }: {
  selected: SearchHit | null; image: string | null; imageBusy: boolean; imageError: string;
  headingRef: RefObject<HTMLHeadingElement | null>; onRetry: () => void;
  regions?: RegionsProps;
}) {
  return <aside className="ws-evidence" aria-labelledby="evidence-heading"><header className="ws-evidence-header"><div><p className="ws-eyebrow">回到原文</p><h2 id="evidence-heading" ref={headingRef} tabIndex={-1}>页面预览</h2></div><span className="ws-original-label">授权原图</span></header>
    {selected ? <><div className="ws-document-heading"><h3>{selected.document_name}</h3><span>第 {selected.page_number} 页</span></div><div className="ws-canvas" aria-busy={imageBusy}>
      {imageBusy && <p className="ws-image-status" role="status"><span className="spinner"/>正在加载页面…</p>}
      {imageError && <div className="ws-image-status" role="alert"><p>{imageError}</p><button type="button" onClick={onRetry}>重试预览</button></div>}
      {image && <RegionCanvas key={selected.page_id} selected={selected} image={image} regions={regions}/>}
      {regions && <RegionControls regions={regions}/>}
    </div></> : <div className="ws-preview-empty"><span aria-hidden="true">▧</span><h3>让证据回到眼前</h3><p>检索后，选择相关页面，<br/>在这里阅读页面原文。</p></div>}
  </aside>;
}

// Presentation state lives here; authentication, requests and private Blob ownership stay in Home.
export function WorkspaceShell(props: WorkspaceProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [historyVisible,setHistoryVisible]=useState(true);
  const [panel, setPanel] = useState<"search" | "preview">("search");
  const [pickerOpen, setPickerOpen] = useState(true);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const menuRef = useRef<HTMLButtonElement | null>(null);
  const newSearchRef = useRef<HTMLButtonElement | null>(null);
  const pickerRef = useRef<HTMLDivElement | null>(null);
  const tasksHeadingRef = useRef<HTMLDivElement | null>(null);
  const accountsHeadingRef = useRef<HTMLDivElement | null>(null);
  const deletionHeadingRef = useRef<HTMLDivElement | null>(null);
  const indexesHeadingRef = useRef<HTMLDivElement | null>(null);
  const auditHeadingRef = useRef<HTMLDivElement | null>(null);
  const sharingHeadingRef = useRef<HTMLDivElement | null>(null);
  function changeView(view: WorkspaceProps["view"]) {
    props.onViewChange(view); setNavigationOpen(false); setPanel("search");
    requestAnimationFrame(() => {
      if (view === "tasks") tasksHeadingRef.current?.querySelector<HTMLInputElement>('input[type="file"]')?.focus();
      else if (view === "accounts") accountsHeadingRef.current?.querySelector<HTMLHeadingElement>('#accounts-heading')?.focus();
      else if (view === "deletion") deletionHeadingRef.current?.querySelector<HTMLHeadingElement>('#deletion-heading')?.focus();
      else if (view === "indexes") indexesHeadingRef.current?.querySelector<HTMLHeadingElement>('#indexes-heading')?.focus();
      else if (view === "audit") auditHeadingRef.current?.querySelector<HTMLHeadingElement>('#audit-heading')?.focus();
      else if (view === "sharing") sharingHeadingRef.current?.querySelector<HTMLHeadingElement>('#sharing-heading')?.focus();
      else inputRef.current?.focus();
    });
  }
  useEffect(() => {
    // A permission/scope error may arrive while the narrow-screen preview is open.
    if (!props.notice) return;
    setPanel("search");
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [props.notice]);
  function newSearch() {
    props.onNewSearch(); setPanel("search"); setNavigationOpen(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }
  function select(hit: SearchHit) {
    props.onSelect(hit); setPanel("preview");
    if (window.matchMedia("(max-width: 1100px)").matches) requestAnimationFrame(() => headingRef.current?.focus());
  }
  function changeScope(mode: SearchMode) {
    if (mode === props.searchMode) return;
    props.onModeChange(mode); setPanel("search"); setPickerOpen(true);
    if (mode === "document") requestAnimationFrame(focusPicker);
  }
  function focusPicker() {
    pickerRef.current?.scrollIntoView({ block: "start" });
    pickerRef.current?.querySelector<HTMLInputElement>('input[type="search"]')?.focus({ preventScroll: true });
  }
  function togglePicker() {
    if (pickerOpen) { setPickerOpen(false); return; }
    setPickerOpen(true); requestAnimationFrame(focusPicker);
  }
  return <div className={`ws-shell ${collapsed ? "ws-is-collapsed" : ""} ${navigationOpen ? "ws-nav-open" : ""} ${historyVisible?'ws-history-visible':'ws-history-hidden'} ws-panel-${panel}`} onKeyDown={event => {
    if (event.key === "Escape" && navigationOpen) { setNavigationOpen(false); menuRef.current?.focus(); }
  }}>
    <WorkspaceSidebar username={props.username} role={props.role} collapsed={collapsed} newSearchRef={newSearchRef} onToggle={() => setCollapsed(value => !value)} onNewSearch={newSearch} onLogout={props.onLogout} view={props.view} onViewChange={changeView}
      historyVisible={historyVisible} onToggleHistory={()=>{setCollapsed(false);setHistoryVisible(v=>collapsed?true:!v);}}
      historyPanel={props.historyPanel?{...props.historyPanel,onOpen:entry=>{props.historyPanel?.onOpen(entry);setNavigationOpen(false);setPanel('search');requestAnimationFrame(()=>inputRef.current?.focus());}}:undefined}/>
    <header className="ws-topbar"><div><button type="button" ref={menuRef} className="ws-icon-button ws-mobile-menu" aria-label={navigationOpen ? "收起导航" : "展开导航"} aria-expanded={navigationOpen} aria-controls="workspace-navigation" onClick={() => {
      setNavigationOpen(value => !value);
      if (!navigationOpen) requestAnimationFrame(() => newSearchRef.current?.focus());
    }}>☰</button><span>{props.view === "indexes" ? "配置身份与回退" : props.view === "audit" ? "审计与任务" : props.view === "deletion" ? "删除与清理" : props.view === "sharing" ? "共享管理" : props.view === "accounts" ? "用户管理" : props.view === "tasks" ? "上传与任务" : props.searchMode === "document" ? "单文档检索" : "文档库检索"}</span><span className="ws-topbar-detail">VISUAL DOCUMENT SEARCH</span></div><div className="ws-topbar-actions"><span className="ws-private-indicator"><i aria-hidden="true"/>授权范围内检索</span><ThemeToggle/></div></header>
    {props.view === "indexes" ? <div className="ws-accounts-slot" ref={indexesHeadingRef}>{props.role === "admin" && props.indexPanel ? <IndexesPanel {...props.indexPanel}/> : <p role="alert">当前账号无配置管理权限。</p>}</div> : props.view === "audit" ? <div className="ws-accounts-slot" ref={auditHeadingRef}>{props.role === "admin" && props.auditPanel ? <AuditPanel {...props.auditPanel}/> : <p role="alert">当前账号无审计查询权限。</p>}</div> : props.view === "deletion" ? <div className="ws-accounts-slot" ref={deletionHeadingRef}>{props.deletionPanel && <DeletionPanel {...props.deletionPanel}/>}</div> : props.view === "sharing" ? <div className="ws-accounts-slot" ref={sharingHeadingRef}>{props.role === "admin" && props.sharingPanel ? <SharingPanel {...props.sharingPanel}/> : <p role="alert">当前账号无共享管理权限。</p>}</div> : props.view === "accounts" ? <div className="ws-accounts-slot" ref={accountsHeadingRef}>{props.role === "admin" && props.accountPanel ? <AccountsPanel {...props.accountPanel}/> : <p role="alert">当前账号无用户管理权限。</p>}</div> : props.view === "tasks" ? <div className="ws-tasks-slot" ref={tasksHeadingRef}><UploadTasksPanel {...props.taskPanel}/></div> : <>
    <div className="ws-view-switch" aria-label="工作区视图"><button type="button" aria-pressed={panel === "search"} aria-controls="workspace-search" onClick={() => setPanel("search")}>问题与结果</button><button type="button" aria-pressed={panel === "preview"} aria-controls="workspace-preview" onClick={() => setPanel("preview")}>页面预览{props.selected ? ` · 第 ${props.selected.page_number} 页` : ""}</button></div>
    <main id="workspace-search" className={`ws-main ${props.result || props.submittedQuestion || props.searchMode === "document" ? "ws-has-activity" : "ws-is-empty"}`} aria-label="文档检索工作区">
      <div className="ws-scope-area"><ScopeSwitch mode={props.searchMode} onChange={changeScope}/>
        {props.searchMode === "document" && <div className="ws-selected-document"><p><span>当前文档</span><strong>{props.targetDocument?.display_name ?? "尚未选择"}</strong>{props.targetDocument && <small>ID {props.targetDocument.document_id.slice(0, 8)} · {props.targetDocument.page_count} 页</small>}</p><button type="button" aria-expanded={pickerOpen || !props.targetDocument} aria-controls="workspace-document-picker" onClick={togglePicker} disabled={!props.targetDocument}>{pickerOpen || !props.targetDocument ? "收起列表" : "更换文档"}</button></div>}
      </div>
      <div className="ws-conversation">{props.searchMode === "document" && (pickerOpen || !props.targetDocument) && <div id="workspace-document-picker" ref={pickerRef}><DocumentPicker {...props.documentPicker} onSelect={document => {
        props.documentPicker.onSelect(document); setPickerOpen(false); setPanel("search"); requestAnimationFrame(() => inputRef.current?.focus());
      }}/></div>}<section className="ws-intro"><p className="ws-eyebrow">LAYOUTPATCH / 文档工作台</p><h1>从问题，<br className="ws-intro-break"/>找到文档里的线索。</h1><p>描述你想了解的内容，<br/>从个人与共享文档中找到相关页面。</p></section>
        {props.historyDetail&&<HistoryBanner detail={props.historyDetail} busy={props.busy||!!props.searchPending} onRepeat={()=>props.onRepeatHistory?.()}/>}
        {props.submittedQuestion && <div className="ws-question"><span>{props.historyDetail?'原问题':'本次问题'}</span><p>{props.submittedQuestion}</p></div>}
        {props.busy && props.submittedQuestion && <div className="ws-search-status" role="status"><span className="spinner"/>正在查找相关页面，首次检索可能需要更久…</div>}
        {props.result && <RetrievalResults result={props.result} selected={props.selected} onSelect={select} historical={!!props.historyDetail}/>}
      </div>
      <div className="ws-composer-area">{props.busy && !props.submittedQuestion && <p className="ws-search-status" role="status">{props.historyPanel?.opening?'正在核对历史引用…':'正在退出登录…'}</p>}{props.notice && <p className="ws-notice" role="alert">{props.notice}</p>}
        {props.searchNotice&&<div className="ws-search-uncertain" role="status"><p>{props.searchNotice}</p>{props.searchPending&&<><button type="button" disabled={props.busy} onClick={props.onVerifySearch}>核对本次提交</button><button type="button" disabled={props.busy} onClick={props.onDismissSearch}>结束核对（可能已保存）</button></>}</div>}
        <QueryComposer question={props.question} busy={props.busy} pending={props.searchPending} queryK={props.queryK} onKChange={props.onKChange} restoredTarget={props.restoredTarget} searchMode={props.searchMode} targetDocument={props.targetDocument} inputRef={inputRef} onQuestionChange={props.onQuestionChange} onSearch={event => { setPanel("search"); props.onSearch(event); }}/><p className="ws-composer-note">每次明确提交保存本人历史 · 相关分数用于排序，请结合原文核对</p></div>
    </main>
    <div className="ws-preview-slot" id="workspace-preview"><EvidencePanel selected={props.selected} image={props.image} imageBusy={props.imageBusy} imageError={props.imageError} headingRef={headingRef} regions={props.regions} onRetry={() => props.selected && props.onSelect(props.selected)}/></div>
    </>}
  </div>;
}
