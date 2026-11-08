import type { HistoryDetail, HistorySummary, SearchResponse } from './api/generated';

// SQLite timestamps are UTC; older naive ISO values must not become local time.
export function historyDate(value: string) {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : value + 'Z');
}

export function groupHistories(items: HistorySummary[], now = new Date()) {
  const day = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  const groups = new Map<string, HistorySummary[]>();
  for (const item of items) {
    const age = (day(now) - day(historyDate(item.created_at))) / 86_400_000;
    const label = item.pinned_at ? '置顶' : age === 0 ? '今天' : age === 1 ? '昨天' : age > 1 && age < 7 ? '过去7天' : '更早';
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(item);
  }
  return [...groups].map(([label, entries]) => ({ label, entries }));
}

/** Keep original rank/score/timings; never fill missing historical hits. */
export function historyResult(detail: HistoryDetail): SearchResponse {
  return { status: detail.entry.result_status, search_mode: detail.search_mode, document_id: detail.document_id,
    profile_id: detail.profile_id, index_generation: detail.index_generation,
    scope_version: detail.current_scope_version, timings_ms: detail.timings_ms, items: detail.items };
}

export function canRepeatHistory(detail: HistoryDetail) {
  return detail.search_mode === 'library' || detail.target_available === true && !!detail.document_id;
}

export function historyCode(error: unknown): string {
  const body = (error as { body?: { detail?: unknown } } | null)?.body;
  return typeof body?.detail === 'string' ? body.detail : '';
}

export function searchFailure(error: unknown) {
  const code = historyCode(error);
  const known: Record<string, string> = {
    HISTORY_LIMIT_REACHED: '历史记录已达1000条上限。请明确删除不需要的记录后，再提交新检索。',
    HISTORY_REQUEST_FAILED: '本次请求已失败，不会自动重新推理。请核对后明确提交一次新检索。',
    HISTORY_REQUEST_INTERRUPTED: '本次请求已中断，不会自动重新推理。请核对后明确提交一次新检索。',
    HISTORY_REQUEST_INPUT_CHANGED: '请求编号与原条件不一致，已停止核对。请重新核对条件。',
    HISTORY_DELETED: '这条历史已删除，同一请求编号不会恢复它。',
  };
  return known[code] ?? '本次提交结果尚未确认，服务器可能仍在处理或已经保存。请用相同编号核对，不要重复新建检索。';
}
