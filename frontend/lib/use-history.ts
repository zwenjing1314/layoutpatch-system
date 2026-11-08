"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, HistoryService } from './api/generated';
import type { HistoryDetail, HistoryList, HistorySummary } from './api/generated';
import { RequestGeneration } from './workspace-lifecycle';
import { boundedTaskRequest } from './task-state';

export type HistoryIntent = { kind: 'rename' | 'delete'; entry: HistorySummary };
type Options = { enabled: boolean; userId: string | null; selectedId: string | null;
  onSessionError: (error: unknown) => void; onOpening: () => void; onOpened: (detail: HistoryDetail) => void;
  onUpdated: (entry: HistorySummary) => void; onUnavailable: (id: string) => void };

export function useHistory(options: Options) {
  const current = useRef(options); current.current = options;
  const lists = useRef(new RequestGeneration()), details = useRef(new RequestGeneration()), writes = useRef(new RequestGeneration());
  const pending = useRef(false), scope = useRef<string | null>(null);
  const [response, setResponse] = useState<HistoryList | null>(null), [offset, setOffset] = useState(0), [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false), [opening, setOpening] = useState<string | null>(null), [actionBusy, setActionBusy] = useState(false);
  const [notice, setNotice] = useState(''), [error, setError] = useState(''), [intent, setIntent] = useState<HistoryIntent | null>(null);
  const cancelOpen = useCallback(() => { details.current.reset(); setOpening(null); }, []);
  const reset = useCallback(() => {
    lists.current.reset(); details.current.reset(); writes.current.reset(); pending.current = false; scope.current = null;
    setResponse(null); setOffset(0); setBusy(false); setOpening(null); setActionBusy(false); setNotice(''); setError(''); setIntent(null);
  }, []);
  function denied(e: unknown) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) { reset(); current.current.onSessionError(e); return true; }
    return false;
  }
  const reload = useCallback(() => { lists.current.reset(); scope.current = null; setResponse(null); setOffset(0); setRefresh(v => v + 1); }, []);
  useEffect(() => { reset(); return () => { lists.current.reset(); details.current.reset(); writes.current.reset(); pending.current = false; }; }, [options.enabled, options.userId, reset]);
  useEffect(() => {
    if (!options.enabled || !options.userId) return;
    const stamp = lists.current.reset(); setBusy(true); setResponse(null); setError('');
    void (async () => {
      try {
        const data = await boundedTaskRequest(HistoryService.listQueryHistory(10, offset), lists.current, 15_000);
        if (!lists.current.accepts(stamp) || !current.current.enabled) return;
        if (offset > 0 && (scope.current !== data.scope_version || !data.items.length)) { reload(); return; }
        scope.current = data.scope_version; setResponse(data);
      } catch (e) { if (lists.current.accepts(stamp) && current.current.enabled && !denied(e)) setError('历史列表暂时无法确认，请刷新。'); }
      finally { if (lists.current.accepts(stamp)) setBusy(false); }
    })();
    return () => { lists.current.reset(); };
    // Identity and enabled are checked again before every private response is applied.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.enabled, options.userId, offset, refresh]);

  async function open(entry: HistorySummary) {
    if (pending.current || !current.current.enabled) return;
    current.current.onOpening();
    const stamp = details.current.reset(); setOpening(entry.history_id); setError(''); setNotice(''); setIntent(null);
    try {
      const detail = await boundedTaskRequest(HistoryService.getQueryHistory(entry.history_id), details.current, 15_000);
      if (!details.current.accepts(stamp) || !current.current.enabled) return;
      if (detail.entry.history_id !== entry.history_id) throw new Error('HISTORY_RESPONSE_MISMATCH');
      current.current.onOpened(detail);
    } catch (e) {
      if (!details.current.accepts(stamp) || !current.current.enabled || denied(e)) return;
      if (e instanceof ApiError && e.status === 404) { current.current.onUnavailable(entry.history_id); reload(); }
      setNotice(e instanceof ApiError && e.status === 404 ? '这条历史已不可用，已清理原结果。' : '历史引用暂时无法确认，未重新检索。请稍后重新打开。');
    } finally { if (details.current.accepts(stamp)) setOpening(null); }
  }

  async function write(entry: HistorySummary, action: 'rename' | 'pin' | 'delete', title?: string) {
    if (pending.current || !current.current.enabled) return;
    pending.current = true; const stamp = writes.current.reset(); setActionBusy(true); setError(''); setNotice('');
    details.current.reset(); setOpening(null); lists.current.reset(); setBusy(false);
    try {
      if (action === 'delete') {
        await boundedTaskRequest(HistoryService.deleteQueryHistory(entry.history_id, { version: entry.version, confirmed: true }), writes.current, 15_000);
      } else {
        const updated = await boundedTaskRequest(HistoryService.updateQueryHistory(entry.history_id, action === 'pin'
          ? { version: entry.version, pinned: entry.pinned_at === null } : { version: entry.version, title }), writes.current, 15_000);
        if (!writes.current.accepts(stamp) || !current.current.enabled) return;
        current.current.onUpdated(updated);
      }
      if (!writes.current.accepts(stamp) || !current.current.enabled) return;
      if (action === 'delete') current.current.onUnavailable(entry.history_id);
      setIntent(null); setNotice(action === 'delete' ? '已删除本人历史；原文档保持不变。' : action === 'pin' ? entry.pinned_at ? '已取消置顶。' : '已置顶。' : '标题已保存，原问题保持不变。'); reload();
    } catch (e) {
      if (!writes.current.accepts(stamp) || !current.current.enabled || denied(e)) return;
      if (action === 'delete' || e instanceof ApiError && e.status === 404) current.current.onUnavailable(entry.history_id);
      setIntent(null); setNotice(e instanceof ApiError && e.status === 409 ? '记录版本已变化，请刷新后重新核对。' : e instanceof ApiError && e.status === 404 ? '这条历史已不可用，请刷新列表。' : '操作结果尚未确认。请先刷新列表或重新打开核对，不会自动重复写入。'); reload();
    } finally { if (writes.current.accepts(stamp)) { pending.current = false; setActionBusy(false); } }
  }
  return { reset, cancelOpen, reload, panel: { response, offset, busy, opening, actionBusy, notice, error, intent, selectedId: options.selectedId,
    onOpen: (entry: HistorySummary) => { void open(entry); },
    onMenu(entry: HistorySummary, kind: 'rename' | 'pin' | 'delete') { if (!pending.current && current.current.enabled) { setError(''); if (kind === 'pin') void write(entry, kind); else setIntent({ kind, entry }); } },
    onClose() { if (!pending.current) { setIntent(null); setError(''); } },
    onSubmit(event: FormEvent<HTMLFormElement>) {
      event.preventDefault(); if (!intent || pending.current) return;
      const data = new FormData(event.currentTarget);
      if (intent.kind === 'delete' && data.get('confirmed') !== 'yes') { setError('请确认只删除这条本人历史。'); return; }
      const title = String(data.get('title') ?? '').trim();
      if (intent.kind === 'rename' && (!title || title.length > 100 || /[\u0000-\u001f\u007f-\u009f]/u.test(title))) { setError('请输入1—100字单行标题。'); return; }
      void write(intent.entry, intent.kind, title);
    },
    onRefresh() { if (!pending.current) reload(); },
    onPrevious() { if (!pending.current && !busy && offset > 0) { lists.current.reset(); setResponse(null); setOffset(v => Math.max(0, v - 10)); } },
    onNext() { if (!pending.current && !busy && response?.next_offset != null) { lists.current.reset(); setResponse(null); setOffset(response.next_offset); } },
  } };
}
export type HistoryProps = ReturnType<typeof useHistory>['panel'];
