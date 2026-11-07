import type { DocumentListItem, SearchResponse } from "@/lib/api/generated";

export type SearchMode = "library" | "document";

/** Selection is an authorized object ID, never a filename or a client-side Top-k filter. */
export function searchDocumentId(mode: SearchMode, document: DocumentListItem | null) {
  if (mode === "library") return undefined;
  if (!document?.searchable || !document.document_version_id) throw new Error("Select a searchable document first");
  return document.document_id;
}

export function matchesSearchTarget(response: SearchResponse, mode: SearchMode, document: DocumentListItem | null) {
  if (response.search_mode !== mode) return false;
  if (mode === "library") return response.document_id === null;
  return !!document?.searchable && response.document_id === document.document_id && response.items.every(hit =>
    hit.document_id === document.document_id && hit.document_version_id === document.document_version_id);
}

export function documentStatus(document: DocumentListItem) {
  if (document.searchable) return "已就绪";
  const statuses: Record<string, string> = {
    receiving: "接收中", queued: "排队中", rendering: "渲染中", encoding: "编码中", indexing: "索引中",
    activating: "激活中", running: "处理中", completed: "待就绪", cancelled: "已取消",
    failed: "处理失败", interrupted: "任务中断", registered: "等待处理", deleted: "已删除",
  };
  return statuses[document.job_status ?? document.status] ?? "暂不可检索";
}

export function unavailableReason(document: DocumentListItem) {
  if (document.searchable) return "";
  const reasons = {
    DOCUMENT_NOT_READY: "尚未完成入库", METADATA_INCOMPLETE: "文档信息不完整",
    INDEX_UNAVAILABLE: "索引暂不可用", INDEX_INCOMPLETE: "页面索引不完整",
  };
  return document.unsearchable_reason ? reasons[document.unsearchable_reason] : "当前不可检索";
}
