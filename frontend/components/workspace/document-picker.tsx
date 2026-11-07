"use client";

import type { DocumentListItem, DocumentListResponse } from "@/lib/api/generated";
import { documentStatus, unavailableReason } from "@/lib/document-selection";
import type { SearchMode } from "@/lib/document-selection";

export type DocumentPickerProps = {
  name: string; response: DocumentListResponse | null; busy: boolean; error: string;
  selected: DocumentListItem | null; page: number;
  onNameChange: (value: string) => void; onSelect: (document: DocumentListItem) => void;
  onPrevious: () => void; onNext: () => void; onRefresh: () => void;
};

export function ScopeSwitch({ mode, onChange }: { mode: SearchMode; onChange: (mode: SearchMode) => void }) {
  return <div className="ws-scope-switch" role="group" aria-label="检索范围">
    <button type="button" aria-pressed={mode === "library"} onClick={() => onChange("library")}>文档库检索</button>
    <button type="button" aria-pressed={mode === "document"} onClick={() => onChange("document")}>单文档检索</button>
  </div>;
}

export function DocumentPicker(props: DocumentPickerProps) {
  return <section className="ws-document-picker" aria-label="授权文档选择" aria-busy={props.busy}>
    <div className="ws-picker-heading"><h2>选择可检索文档</h2><button type="button" onClick={props.onRefresh} disabled={props.busy}>刷新列表</button></div>
    <label htmlFor="document-name">按文件名筛选</label>
    <input id="document-name" type="search" maxLength={255} value={props.name} onChange={event => props.onNameChange(event.target.value)} placeholder="输入文件名片段，例如 gemm" autoComplete="off" aria-describedby="document-name-help"/>
    <p id="document-name-help" className="ws-picker-help">只匹配文件名，忽略英文大小写；内容问题在下方输入。筛选不会更换已选文件。</p>
    {props.busy && <p role="status" className="ws-picker-status">正在加载授权文档…</p>}
    {props.error && <p role="alert" className="ws-picker-error">{props.error}</p>}
    {props.response && <><fieldset className="ws-document-options"><legend className="sr-only">可见文档，只有就绪文档可选</legend>
      {props.response.items.map(document => <label key={document.document_id} className={`ws-document-option ${props.selected?.document_id === document.document_id ? "is-selected" : ""} ${document.searchable ? "" : "is-unavailable"}`}>
        <input type="radio" name="selected-document" value={document.document_id} checked={props.selected?.document_id === document.document_id} disabled={!document.searchable} onChange={() => props.onSelect(document)}/>
        <span className="ws-document-copy"><strong>{document.display_name}</strong><span>{document.access === "own" ? "本人" : "共享"} · {document.page_count ?? "待确认"} 页 · {documentStatus(document)}</span>
          <small>ID {document.document_id.slice(0, 8)} · {document.created_at.replace("T", " ").slice(0, 16)}{!document.searchable && ` · ${unavailableReason(document)}`}</small></span>
      </label>)}
    </fieldset>
      {!props.response.items.length && <p role="status" className="ws-picker-status">{props.name.trim() ? "没有匹配的文件名，请调整筛选。" : "当前没有可见文档。"}</p>}
    </>}
    <div className="ws-document-pagination"><button type="button" onClick={props.onPrevious} disabled={props.busy || props.page === 1 || !props.response}>上一页</button><span aria-live="polite">第 {props.page} 页</span><button type="button" onClick={props.onNext} disabled={props.busy || !props.response?.next_cursor}>下一页</button></div>
  </section>;
}
