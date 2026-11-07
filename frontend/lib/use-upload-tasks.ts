"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, DocumentsService } from "@/lib/api/generated";
import type { JobListResponse, JobResponse } from "@/lib/api/generated";
import type { UploadTasksProps } from "@/components/workspace/upload-tasks";
import { RequestGeneration } from "@/lib/workspace-lifecycle";
import { boundedTaskRequest, taskActive } from "@/lib/task-state";

type Options = {
  enabled: boolean; userId: string | null; csrfToken?: string;
  onSessionError: (error: unknown) => void; onChanged: () => void; onBrowse: (job: JobResponse) => void;
};

export function useUploadTasks(options: Options) {
  const current = useRef(options); current.current = options;
  const uploadGeneration = useRef(new RequestGeneration()), listGeneration = useRef(new RequestGeneration()), actionGeneration = useRef(new RequestGeneration());
  const reservation = useRef<{ file: File; key: string } | null>(null);
  const observed = useRef(new Map<string, string>());
  const [filename, setFilename] = useState(""), [inputKey, setInputKey] = useState(0);
  const [uploadBusy, setUploadBusy] = useState(false), [uploadError, setUploadError] = useState(""), [uploadUncertain, setUploadUncertain] = useState(false);
  const [jobs, setJobs] = useState<JobListResponse | null>(null), [listBusy, setListBusy] = useState(false), [listError, setListError] = useState("");
  const [paused, setPaused] = useState(false), [cursors, setCursors] = useState<(string | null)[]>([null]), [refresh, setRefresh] = useState(0);
  const [actionBusy, setActionBusy] = useState<string | null>(null), [actionError, setActionError] = useState("");

  const reset = useCallback(() => {
    uploadGeneration.current.reset(); listGeneration.current.reset(); actionGeneration.current.reset();
    reservation.current = null; observed.current.clear(); setFilename(""); setInputKey(value => value + 1);
    setUploadBusy(false); setUploadError(""); setUploadUncertain(false); setJobs(null); setListBusy(false); setListError("");
    setActionBusy(null); setActionError(""); setPaused(false); setCursors([null]);
  }, []);
  const refreshTasks = useCallback(() => { setListError(""); setActionError(""); setPaused(false); setCursors([null]); setRefresh(value => value + 1); }, []);
  function authError(error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) { current.current.onSessionError(error); return true; }
    return false;
  }
  useEffect(() => {
    reset();
    return () => { uploadGeneration.current.reset(); listGeneration.current.reset(); actionGeneration.current.reset(); reservation.current = null; };
  }, [options.enabled, options.userId, reset]);

  useEffect(() => {
    if (!options.enabled || !options.userId) return;
    const stamp = listGeneration.current.reset(), deadline = Date.now() + 600_000;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      setListBusy(true);
      try {
        const response = await boundedTaskRequest(DocumentsService.listJobs(10, cursors[cursors.length - 1]), listGeneration.current, 15_000);
        if (!listGeneration.current.accepts(stamp)) return;
        let changed = false;
        for (const job of response.items) {
          const before = observed.current.get(job.job_id), after = `${job.attempt}:${job.status}`;
          if (before && before !== after && !taskActive(job)) changed = true;
          observed.current.set(job.job_id, after);
        }
        setJobs(response); setListError("");
        if (changed) current.current.onChanged();
        if (response.items.some(taskActive)) {
          if (Date.now() < deadline) timer = setTimeout(poll, 2500);
          else setPaused(true);
        }
      } catch (error) {
        if (!listGeneration.current.accepts(stamp)) return;
        setJobs(null); setPaused(true);
        if (!authError(error)) setListError("任务状态暂时无法确认，请刷新任务。服务端任务不会因网页停止等待而自动取消。");
      } finally { if (listGeneration.current.accepts(stamp)) setListBusy(false); }
    }
    void poll();
    return () => { clearTimeout(timer); listGeneration.current.reset(); };
    // Callbacks use current refs; polling never cancels a content search or upload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.enabled, options.userId, cursors, refresh]);

  const panel: UploadTasksProps = {
    filename, inputKey, uploadBusy, uploadError, uploadUncertain, jobs, listBusy, listError, paused, page: cursors.length, actionBusy, actionError,
    onFile(file) {
      uploadGeneration.current.reset(); reservation.current = null; setFilename(""); setUploadError(""); setUploadUncertain(false);
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".pdf") || !file.size || file.size > 20 * 1024 * 1024) { setUploadError("请选择非空PDF，大小不超过20 MiB；页数由服务器核验。"); return; }
      reservation.current = { file: file.type === "application/pdf" ? file : new File([file], file.name, { type: "application/pdf" }), key: crypto.randomUUID() };
      setFilename(file.name);
    },
    async onUpload(event) {
      event.preventDefault();
      const selected = reservation.current;
      if (!selected || !current.current.enabled || !current.current.csrfToken || uploadBusy) return;
      const stamp = uploadGeneration.current.reset(); setUploadBusy(true); setUploadError("");
      try {
        const job = await boundedTaskRequest(DocumentsService.uploadPdf(selected.key, current.current.csrfToken, { file: selected.file }), uploadGeneration.current, 45_000);
        if (!uploadGeneration.current.accepts(stamp)) return;
        observed.current.set(job.job_id, `${job.attempt}:${job.status}`);
        reservation.current = null; setFilename(""); setInputKey(value => value + 1); setUploadUncertain(false);
        current.current.onChanged(); refreshTasks();
      } catch (error) {
        if (!uploadGeneration.current.accepts(stamp) || authError(error)) return;
        const detail = error instanceof ApiError ? (error.body as { detail?: string })?.detail : null;
        const rejected = error instanceof ApiError && [413, 415, 422].includes(error.status);
        setUploadUncertain(!rejected);
        setUploadError(rejected ? ({ PDF_TOO_MANY_PAGES: "PDF超过100页上限，请选择较小文件。", PDF_TOO_LARGE: "PDF超过20 MiB上限。", ENCRYPTED_PDF: "暂不接受加密PDF。" }[detail ?? ""] ?? "文件格式或内容不符合要求，请重新选择有效PDF。") : "发送结果未确认。可刷新任务，或用同一上传标识重试发送；不会主动创建重复文档。");
        refreshTasks();
      } finally { if (uploadGeneration.current.accepts(stamp)) setUploadBusy(false); }
    },
    onStopUpload() {
      uploadGeneration.current.reset(); setUploadBusy(false); setUploadUncertain(true);
      setUploadError("已停止等待发送，服务端可能已接收。请刷新任务或用同一上传标识重试发送确认。"); refreshTasks();
    },
    onRefresh: refreshTasks,
    onPrevious() { if (!listBusy && cursors.length > 1) { setJobs(null); setCursors(value => value.slice(0, -1)); } },
    onNext() { if (!listBusy && jobs?.next_cursor) { const next = jobs.next_cursor; setJobs(null); setCursors(value => [...value, next]); } },
    async onAction(job, action) {
      if (actionBusy || !current.current.enabled) return;
      const stamp = actionGeneration.current.reset(); setActionBusy(job.job_id); setActionError("");
      try {
        const request = action === "retry" ? DocumentsService.retryJob(job.job_id, { attempt: job.attempt }) : DocumentsService.cancelJob(job.job_id, { attempt: job.attempt });
        const updated = await boundedTaskRequest(request, actionGeneration.current, 15_000);
        if (!actionGeneration.current.accepts(stamp)) return;
        observed.current.set(updated.job_id, `${updated.attempt}:${updated.status}`);
        current.current.onChanged(); refreshTasks();
      } catch (error) {
        if (!actionGeneration.current.accepts(stamp) || authError(error)) return;
        const detail = error instanceof ApiError ? (error.body as { detail?: string })?.detail : null;
        setActionError(detail === "REUPLOAD_REQUIRED" ? "源文件缺失或校验不符，请重新上传PDF。" : "操作结果待确认或任务已变化。请先刷新任务，再按最新尝试编号操作。");
        setRefresh(value => value + 1);
      } finally { if (actionGeneration.current.accepts(stamp)) setActionBusy(null); }
    },
    onBrowse(job) { current.current.onBrowse(job); },
  };
  return { panel, reset };
}
