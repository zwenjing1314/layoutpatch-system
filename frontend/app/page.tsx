"use client";
import { useState } from "react";
import "@/lib/api/client";
import { SystemService } from "@/lib/api/generated";
export default function Home() {
  const [status, setStatus] = useState("尚未检查");
  async function check() {
    setStatus("检查中…");
    try {
      const result = await SystemService.getHealth();
      setStatus(result.status === "ok" ? "服务连接正常" : "服务响应异常");
    } catch { setStatus("暂时无法连接服务，请稍后重试"); }
  }
  return <main><p className="eyebrow">LAYOUTPATCH</p><h1>视觉文档检索<br/>与证据定位系统</h1>
    <p>系统正在建设中，文档检索功能将在后续开放。</p>
    <section><h2>服务连接</h2><p role="status" aria-live="polite">{status}</p>
    <button onClick={check}>检查连接</button></section></main>;
}
