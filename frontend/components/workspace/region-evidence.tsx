"use client";
import { useState } from 'react';
import type { SearchHit } from '@/lib/api/generated';
import type { RegionsProps } from '@/lib/use-regions';
import { inferenceFailed } from '@/lib/region-state';

const labels:Record<string,string>={text:'文字',title:'标题',image:'图像',table:'表格',equation:'公式'};
const statuses:Record<string,string>={not_requested:'尚未解析',queued:'解析排队中',running:'正在解析',ready:'候选已就绪',no_candidates:'此页没有解析候选',failed:'证据处理失败',timeout:'解析超时',interrupted:'解析已中断',unavailable:'此页缺少可用的完整特征'};

export function RegionControls({regions}:{regions:RegionsProps}) {
  const {state,response,busy,error,chosen}=regions;
  return <section className="ws-region-controls" aria-label="页内证据定位"><div className="ws-region-heading"><h3>页内证据 · D-no-text</h3><span role="status">{busy?'处理中…':state?statuses[state.status]:'正在核对证据状态…'}</span></div>
    <p>在真实解析候选中排序，请结合原文核对。</p>
    <div className="ws-region-actions"><button type="button" onClick={regions.onRefresh} disabled={busy}>刷新状态</button>
      {state?.can_parse && !inferenceFailed(state) && ['not_requested','failed','timeout','interrupted'].includes(state.status) && <button type="button" onClick={regions.onParse} disabled={busy}>{state.status==='not_requested'?'解析此文档':'重试文档解析'}</button>}
      {(state?.status==='ready'||inferenceFailed(state)) && <button type="button" onClick={regions.onLocate} disabled={busy}>{inferenceFailed(state)?'重试定位证据':response?'重新定位证据':'定位证据'}</button>}
    </div>
    {state?.status==='not_requested'&&!state.can_parse&&<p>此共享文档尚未解析，请由文档所有者准备候选。</p>}
    {state?.error_code&&<p className="ws-region-warning">{state.error_code} · 原图仍可阅读。</p>}
    {error&&<p className="ws-region-warning" role="alert">{error}</p>}
    {response&&<><ol className="ws-region-list">{response.items.slice(0,5).map(item=><li key={item.candidate_id}><button type="button" aria-pressed={chosen===item.layout_id} onClick={()=>regions.onChoose(item)}>
      <strong>#{item.rank} {labels[item.type]}</strong><span>候选 {item.layout_id} · 分数 {item.score.toFixed(4)}</span></button><button type="button" onClick={()=>regions.onCrop(item)}>查看裁剪 #{item.rank}</button></li>)}</ol>
      <small>第 {response.page_number} 页 · 候选 {response.candidate_hash?.slice(0,8)} · 模型 {response.model_profile_sha256.slice(0,8)}</small></>}
    {regions.cropBusy&&<p role="status">正在获取授权裁剪…</p>}
    {regions.cropError&&<p className="ws-region-warning" role="alert">{regions.cropError}</p>}
    {regions.crop&&<figure className="ws-region-crop"><img src={regions.crop} alt={`授权候选 ${chosen} 裁剪`}/><figcaption>候选 {chosen} · 按原图像素向外取整裁剪</figcaption></figure>}
  </section>;
}

export function RegionCanvas({selected,image,regions}:{selected:SearchHit;image:string;regions?:RegionsProps}) {
  const [zoom,setZoom]=useState(1);
  const active=regions?.response?.page_id===selected.page_id&&regions.response.render_sha256===selected.render_sha256
    ?regions.response.items.find(item=>item.layout_id===regions.chosen):undefined;
  return <><div className="ws-zoom-controls" aria-label="页面缩放"><label>缩放 <select aria-label="页面缩放比例" value={zoom} onChange={event=>setZoom(Number(event.target.value))}>
    <option value={.5}>50%</option><option value={1}>100%</option><option value={1.5}>150%</option></select></label><span>{active?`高亮候选 ${active.layout_id} · ${labels[active.type]}`:'选择证据后显示高亮'}</span></div>
    <div className="ws-zoom-viewport"><div className="ws-page-frame" style={{width:`${zoom*100}%`}} data-page-id={selected.page_id}>
      <img src={image} alt={`${selected.document_name}，第 ${selected.page_number} 页原文`} width={selected.width_px} height={selected.height_px}/>
      {active&&<svg className="ws-region-overlay" viewBox={`0 0 ${selected.width_px} ${selected.height_px}`} aria-label={`第 ${selected.page_number} 页候选 ${active.layout_id} 高亮`} role="img">
        <rect data-candidate-id={active.candidate_id} x={active.bbox[0]} y={active.bbox[1]} width={active.bbox[2]-active.bbox[0]} height={active.bbox[3]-active.bbox[1]} vectorEffect="non-scaling-stroke"/>
      </svg>}
    </div></div></>;
}
