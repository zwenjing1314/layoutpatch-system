"use client";
import type { AuditProps } from '@/lib/use-audit';
import type { AuditEventItem, AuditTaskItem } from '@/lib/api/generated';

const labels:Record<string,string>={index:'索引',started:'开始',verify:'验证',rebuild:'重建',activate:'切换',account:'账号',sharing:'共享',deletion:'删除',history:'历史',ingest:'入库',parsing:'解析',cleanup:'清理',search:'检索',success:'成功',noop:'未变更',rejected:'拒绝',failed:'失败',interrupted:'中断',partial:'部分完成',receiving:'接收中',queued:'排队中',running:'运行中',completed:'完成',ready:'就绪',cancelled:'已取消',deleted:'已删除',create:'创建',update:'更新',delete:'删除',enable:'启用',disable:'停用',reset:'重置',revoke:'撤销会话',publish:'发布',unpublish:'撤回',retry:'重试'};
export function AuditPanel(props:AuditProps){
  const events=props.tab==='events',sources=events?['account','sharing','deletion','history','index']:['ingest','parsing','cleanup','search','index'];
  const states=events?['success','noop','rejected','failed','started']:['receiving','queued','running','completed','ready','partial','failed','interrupted','cancelled','deleted'];
  return <main className="ws-accounts ws-audit" aria-labelledby="audit-heading"><header className="ws-accounts-heading"><div><p className="ws-eyebrow">管理与运行记录</p><h1 id="audit-heading" tabIndex={-1}>审计与任务</h1><p>仅查询必要操作元数据。私人问题、标题和文档内容不在此展示。</p></div></header>
    <div className="ws-audit-tabs" role="group" aria-label="查询类型"><button type="button" aria-pressed={events} onClick={()=>props.onTab('events')}>操作事件</button><button type="button" aria-pressed={!events} onClick={()=>props.onTab('tasks')}>任务状态</button></div>
    <form key={props.formKey+props.tab} className="ws-audit-filters" aria-label="审计筛选" onSubmit={props.onSubmit}>
      <label>开始日期（UTC）<input name="start" type="date" defaultValue={props.filters.start} required/></label><label>结束日期（含，UTC）<input name="end" type="date" defaultValue={props.filters.end} required/></label>
      <label>{events?'事件类别':'任务类型'}<select name="source" defaultValue={props.filters.source}><option value="">全部</option>{sources.map(s=><option key={s} value={s}>{labels[s]}</option>)}</select></label>
      <label>{events?'操作结果':'任务状态'}<select name="state" defaultValue={props.filters.state}><option value="">全部</option>{states.map(s=><option key={s} value={s}>{labels[s]}</option>)}</select></label>
      <label>{events?'操作者ID':'所有者ID'}<input name="actor" type="text" maxLength={36} defaultValue={props.filters.actor} placeholder="完整UUID，可留空"/></label><label>{events?'对象ID':'文档ID'}<input name="target" type="text" maxLength={36} defaultValue={props.filters.target} placeholder="完整UUID，可留空"/></label>
      <div><button type="submit" disabled={props.busy}>应用筛选</button><button type="button" onClick={props.onRefresh} disabled={props.busy}>刷新查询</button></div>
    </form><p className="ws-account-help">默认近7个UTC日 · 单次最多31天 · 每页10条 · {events?'按事件时间排序':'按最近更新时间排序，仅显示当前任务状态'}。系统与本地CLI操作以对应身份标注。</p>
    <details className="ws-audit-policy"><summary>记录保留与隐私边界</summary><p>最小操作事件与无正文去重标记随当前数据库保留，不自动过期。个人问题、标题及结果引用由本人显式删除；最小事件与删除标记继续保留。文档物理清理可移除关联任务，清理事件仍保留。此页不提供正文查看、任务重试或删除操作；已交付内容和独立备份无法远程收回。</p></details>
    {props.error&&<p role="alert" className="ws-task-warning">{props.error}</p>}{props.notice&&<p role="status">{props.notice}</p>}{props.busy&&<p role="status">正在读取{events?'操作事件':'任务状态'}…</p>}
    {props.response&&!props.response.items.length&&<p role="status">当前范围没有匹配记录。可调整日期或筛选条件。</p>}
    <section aria-label={events?'操作事件列表':'任务状态列表'} className="ws-account-cards" aria-busy={props.busy}>{props.response?.items.map(item=>{
      if(events){const e=item as AuditEventItem;return <article className="ws-account-card" key={e.category+e.event_id}><h2>{labels[e.category]} · {labels[e.action]??e.action} · {labels[e.outcome]}</h2><p>{new Date(e.occurred_at*1000).toLocaleString('zh-CN')}</p><p>操作者：{e.actor_type==='cli'?'本地CLI':e.actor_type==='system'?'系统':e.actor_id}</p><p>对象ID：{e.target_id??'未关联对象'}</p><p>结果码：{e.code==='OTHER'?'其他（详细原因未公开）':e.code}</p><small>事件ID：{e.event_id}</small></article>;}
      const t=item as AuditTaskItem;return <article className="ws-account-card" key={t.kind+t.task_id}><h2>{labels[t.kind]} · {labels[t.status]}</h2><p>任务ID：{t.task_id}</p><p>所有者ID：{t.owner_id}</p><p>文档ID：{t.document_id??'不公开关联文档'}</p><p>尝试 {t.attempt} · 阶段 {t.stage}{t.progress!=null?` · ${t.progress}%`:''}</p><p>结果码：{t.error_code==='OTHER'?'其他（详细原因未公开）':t.error_code??'无'}</p><p>创建：{t.created_at??'不可用'}<br/>更新：{t.updated_at??'不可用'}</p></article>;
    })}</section><nav className="ws-account-pagination" aria-label="审计分页"><button type="button" disabled={props.busy||props.offset===0} onClick={props.onPrevious}>上一页</button><span>第 {Math.floor(props.offset/10)+1} 页</span><button type="button" disabled={props.busy||props.response?.next_offset==null} onClick={props.onNext}>下一页</button></nav>
  </main>;
}
