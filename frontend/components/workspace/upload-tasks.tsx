"use client";

import type { FormEvent } from "react";
import type { JobListResponse, JobResponse } from "@/lib/api/generated";
import { taskError, taskStatus } from "@/lib/task-state";

export type UploadTasksProps = {
  filename: string; inputKey: number; uploadBusy: boolean; uploadError: string; uploadUncertain: boolean;
  jobs: JobListResponse | null; listBusy: boolean; listError: string; paused: boolean; page: number;
  actionBusy: string | null; actionError: string;
  onFile: (file: File | null) => void; onUpload: (event: FormEvent<HTMLFormElement>) => void; onStopUpload: () => void;
  onRefresh: () => void; onPrevious: () => void; onNext: () => void;
  onAction: (job: JobResponse, action: "retry" | "cancel") => void; onBrowse: (job: JobResponse) => void;
};

export function UploadTasksPanel(props: UploadTasksProps) {
  return <main className="ws-tasks-main" aria-label="本人上传与任务"><div className="ws-tasks-content">
    <header className="ws-tasks-heading"><p className="ws-eyebrow">LAYOUTPATCH / 私有文档入库</p><h1>上传与任务</h1><p>上传后由服务端完整渲染、编码并核验；全部完成后才能检索。文件默认仅本人可见。</p></header>
    <form className="ws-upload-form" onSubmit={props.onUpload} aria-label="上传PDF"><label htmlFor="upload-pdf">选择一份PDF</label>
      <input key={props.inputKey} id="upload-pdf" name="file" type="file" accept=".pdf,application/pdf" disabled={props.uploadBusy} onChange={event => props.onFile(event.target.files?.[0] ?? null)} aria-describedby="upload-help"/>
      <p id="upload-help">上限20 MiB、100页。格式与页数由服务端核验；文件不会发送到外部模型。</p>
      {props.filename && <p className="ws-upload-filename">待发送：{props.filename}</p>}
      {props.uploadError && <p className="ws-task-warning" role="alert">{props.uploadError}</p>}
      <div className="ws-task-controls"><button type="submit" disabled={props.uploadBusy || !props.filename}>{props.uploadBusy ? "上传并校验中…" : props.uploadUncertain ? "同标识重试发送" : "上传并创建任务"}</button>
        {props.uploadBusy && <button type="button" onClick={props.onStopUpload}>停止等待发送</button>}</div>
    </form>
    <section className="ws-job-list" aria-label="本人持久任务" aria-busy={props.listBusy}><div className="ws-job-list-heading"><h2>本人任务</h2><button type="button" onClick={props.onRefresh} disabled={props.listBusy}>刷新任务</button></div>
      <p className="ws-tasks-help">刷新或重新登录后从服务器恢复。运行中取消需等待安全检查点；当前GPU操作可能继续到完成。每项最多10次尝试。</p>
      {props.listBusy && !props.jobs && <p role="status">正在读取本人任务…</p>}
      {props.listError && <p className="ws-task-warning" role="alert">{props.listError}</p>}
      {props.actionError && <p className="ws-task-warning" role="alert">{props.actionError}</p>}
      {props.paused && !props.listError && <p role="status">自动检查已暂停；任务继续在服务器运行，可刷新任务重新确认。</p>}
      {props.jobs && !props.jobs.items.length && <p role="status">当前没有本人上传任务。</p>}
      <div className="ws-job-cards">{props.jobs?.items.map(job => <article key={job.job_id} className="ws-job-card" aria-label={`任务 ${job.job_id.slice(0, 8)}`}>
        <div className="ws-job-title"><h3>{job.display_name}</h3><strong className={`ws-job-status ws-job-${job.status}`}>{taskStatus(job)}</strong></div>
        <p className="ws-job-meta">{job.page_count} 页 · 私有 · 任务 {job.job_id.slice(0, 8)} · 第 {job.attempt} 次尝试</p>
        <progress max={100} value={job.progress} aria-label={`${job.display_name}处理进度`}/><p className="ws-job-meta">处理进度 {job.progress}% · 最后更新 {job.updated_at.replace("T", " ").slice(0, 19)}</p>
        {job.error_code && <p className="ws-task-warning">{taskError(job.error_code)}<small>错误码：{job.error_code}</small></p>}
        {job.cancel_requested_at && job.status === "running" && <p role="status">取消请求已保存。最终激活前会再次核验，当前操作结束前不会显示为已取消。</p>}
        <div className="ws-task-controls">
          {job.cancel_available && <button type="button" disabled={!!props.actionBusy} onClick={() => props.onAction(job, "cancel")}>{props.actionBusy === job.job_id ? "正在提交…" : "取消任务"}</button>}
          {job.retry_available && <button type="button" disabled={!!props.actionBusy} onClick={() => props.onAction(job, "retry")}>{props.actionBusy === job.job_id ? "正在提交…" : "重试此任务"}</button>}
          {job.status === "completed" && <button type="button" onClick={() => props.onBrowse(job)}>到文档列表选择检索</button>}
          {["failed", "interrupted", "cancelled"].includes(job.status) && !job.retry_available && <span className="ws-tasks-help">当前不可重试，请重新选择源PDF上传或核对任务状态。</span>}
        </div>
        <details className="ws-attempt-history"><summary>尝试记录（{job.attempts.length}）</summary><ol>{job.attempts.map(attempt => <li key={attempt.attempt}>
          <strong>第 {attempt.attempt} 次 · {taskStatus(attempt)}</strong><span>进度 {attempt.progress}%{attempt.error_code ? ` · ${attempt.error_code}` : ""}</span><span>{attempt.created_at.replace("T", " ").slice(0, 19)}{attempt.ended_at ? ` 至 ${attempt.ended_at.replace("T", " ").slice(0, 19)}` : " · 尚未结束"}</span>
        </li>)}</ol></details>
      </article>)}</div>
      <div className="ws-document-pagination"><button type="button" disabled={props.listBusy || props.page === 1} onClick={props.onPrevious}>上一页任务</button><span aria-live="polite">第 {props.page} 页</span><button type="button" disabled={props.listBusy || !props.jobs?.next_cursor} onClick={props.onNext}>下一页任务</button></div>
    </section>
  </div></main>;
}
