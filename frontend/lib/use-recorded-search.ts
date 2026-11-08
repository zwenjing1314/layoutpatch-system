"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, HistoryService } from './api/generated';
import type { HistoryDetail, HistorySearchInput } from './api/generated';
import { RequestGeneration } from './workspace-lifecycle';
import { boundedTaskRequest } from './task-state';
import { historyCode, searchFailure } from './history-state';

type Options = { enabled: boolean; userId: string | null; onStart: (body: HistorySearchInput) => void;
  onResult: (detail: HistoryDetail, replayed: boolean) => void; onSessionError: (error: unknown) => void };

export function useRecordedSearch(options: Options) {
  const current = useRef(options); current.current = options;
  const requests = useRef(new RequestGeneration()), active = useRef(false);
  const bodyRef = useRef<HistorySearchInput | null>(null);
  const [pending, setPending] = useState(false), [busy, setBusy] = useState(false), [notice, setNotice] = useState('');
  const reset = useCallback(() => {
    requests.current.reset(); active.current = false; bodyRef.current = null;
    setPending(false); setBusy(false); setNotice('');
  }, []);
  const cancel = useCallback(() => {
    requests.current.reset(); active.current = false; setBusy(false);
    if (bodyRef.current) setNotice(searchFailure(null));
  }, []);
  useEffect(() => { reset(); return () => { requests.current.reset(); active.current = false; bodyRef.current = null; }; }, [options.enabled, options.userId, reset]);

  async function execute(body: HistorySearchInput) {
    if (active.current || !current.current.enabled || !current.current.userId) return;
    current.current.onStart(body);
    const stamp = requests.current.reset(); active.current = true; bodyRef.current = body;
    setBusy(true); setPending(true); setNotice('');
    try {
      // A finite wait is not cancellation of model work. Only explicit same-ID verification may retry.
      const response = await boundedTaskRequest(HistoryService.searchAndRecordHistory(body), requests.current, 240_000);
      if (!requests.current.accepts(stamp) || !current.current.enabled) return;
      const detail = response.history;
      if (detail.q !== body.q || detail.k !== body.k || detail.search_mode !== (body.document_id ? 'document' : 'library') ||
          detail.document_id !== (body.document_id ?? null) && detail.target_available !== false) throw new Error('HISTORY_RESPONSE_MISMATCH');
      bodyRef.current = null; setPending(false); setNotice('');
      current.current.onResult(detail, response.replayed ?? false);
    } catch (error) {
      if (!requests.current.accepts(stamp) || !current.current.enabled) return;
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) { reset(); current.current.onSessionError(error); return; }
      const status = error instanceof ApiError ? error.status : 0, code = historyCode(error);
      const definite = [404, 410, 422].includes(status) || status === 409 && code !== 'HISTORY_REQUEST_PENDING';
      if (definite) { bodyRef.current = null; setPending(false); }
      setNotice(status === 404 ? '原检索目标已不可用，请重新选择文档。' : status === 422 ? '提交条件无效，请核对问题、目标和返回页数。' : searchFailure(error));
    } finally { if (requests.current.accepts(stamp)) { active.current = false; setBusy(false); } }
  }
  return { reset, cancel, busy, pending, notice,
    submit(q: string, k: number, documentId?: string | null) {
      if (active.current || bodyRef.current || !current.current.enabled) return;
      if (!q.trim() || q.trim().length > 2000 || !Number.isInteger(k) || k < 1 || k > 50) { setNotice('请核对问题长度和返回页数。'); return; }
      return execute({ q: q.trim(), k, document_id: documentId ?? null, request_id: crypto.randomUUID() });
    },
    verify() { if (bodyRef.current) return execute(bodyRef.current); },
    dismiss() { if (!active.current) { bodyRef.current = null; setPending(false); setNotice('已结束本地核对，服务器可能已保存原记录。下一次提交会创建新记录，请先查看历史。'); } },
  };
}
