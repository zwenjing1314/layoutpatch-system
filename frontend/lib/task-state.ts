import type { JobResponse } from "@/lib/api/generated";

export const taskActive = (job: JobResponse) => ["receiving", "queued", "running"].includes(job.status);
export function taskStatus(job: Pick<JobResponse, "status" | "stage" | "cancel_requested_at">) {
  if (job.cancel_requested_at && job.status === "running") return "等待取消检查点";
  const stages: Record<string, string> = { upload: "接收文件", pending: "等待处理", rendering: "渲染页面", encoding: "编码页面", indexing: "写入候选索引", activating: "核验并激活" };
  const statuses: Record<string, string> = { receiving: "接收中", queued: "排队中", completed: "已完成", failed: "处理失败", interrupted: "处理中断", cancelled: "已取消" };
  return job.status === "running" ? stages[job.stage] ?? "处理中" : statuses[job.status] ?? "状态待确认";
}

export function taskError(code: string | null) {
  if (!code) return "";
  const messages: Record<string, string> = {
    CANCELLED_BY_OWNER: "已按本人请求取消，未激活半成品。", INGEST_INTERRUPTED: "处理因服务停止而中断，可显式重试。",
    UPLOAD_INTERRUPTED: "接收文件时中断；源文件不完整时请重新上传。", UPLOAD_WRITE_FAILED: "文件保存失败，请重新上传。",
    UPLOAD_NOT_COMMITTED: "文件接收未完成提交，请重新上传。", PAGE_ENCODING_FAILED: "页面编码失败，可在服务恢复后重试。",
    INDEX_UNAVAILABLE: "索引服务暂不可用，旧文档仍可保留。", RENDER_FAILED: "PDF页面渲染失败。", RENDER_TIMEOUT: "页面渲染超时。",
    MODEL_BUSY: "模型等待超时，请稍后重试。", INGEST_DEADLINE_EXCEEDED: "本次尝试超过处理时限，已在检查点停止。",
    INGEST_AUTHORITY_CHANGED: "文档归属、状态或处理权限已变化。", INGEST_STORAGE_FAILED: "处理产物保存失败。",
    METADATA_UNAVAILABLE: "任务元数据暂不可用。",
  };
  return messages[code] ?? "本次处理未完成，请核对错误码后重试或重新上传。";
}

type Cancelable<T> = PromiseLike<T> & { cancel(): void };
type Generation = { track(cancel: () => void): () => void };

/** A stopped HTTP wait never claims that a server/GPU operation was cancelled. */
export function boundedTaskRequest<T>(request: Cancelable<T>, generation: Generation, milliseconds: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  let release = () => {};
  const result = new Promise<T>((resolve, reject) => {
    timer = setTimeout(() => { request.cancel(); reject(new Error("TASK_REQUEST_TIMEOUT")); }, milliseconds);
    release = generation.track(() => { request.cancel(); reject(new Error("TASK_REQUEST_CANCELLED")); });
    Promise.resolve(request).then(resolve, reject);
  });
  return result.finally(() => { clearTimeout(timer); release(); });
}
