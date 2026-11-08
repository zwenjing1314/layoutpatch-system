"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, DocumentsService, PagesService } from "./api/generated";
import type { RegionItem, RegionResponse, RegionState, SearchHit } from "./api/generated";
import { RequestGeneration } from "./workspace-lifecycle";
import { matchesRegionPage, privateCropPath, validRegions } from "./region-state";

export function useRegions({ enabled, selected, index, question, onError }: {
  enabled: boolean; selected: SearchHit | null; index?: string; question: string; onError: (error: unknown) => void;
}) {
  const [state, setState] = useState<RegionState | null>(null);
  const [response, setResponse] = useState<RegionResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [crop, setCrop] = useState<string | null>(null);
  const [cropBusy, setCropBusy] = useState(false);
  const [cropError, setCropError] = useState("");
  const [chosen, setChosen] = useState<number | null>(null);
  const generation = useRef(new RequestGeneration());
  const cropGeneration = useRef(new RequestGeneration());
  const cropUrl = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const deadline = useRef(0);
  const handleError = useRef(onError); handleError.current = onError;
  const clearCrop = useCallback(() => {
    cropGeneration.current.reset(); if (cropUrl.current) URL.revokeObjectURL(cropUrl.current);
    cropUrl.current = null; setCrop(null); setCropBusy(false); setCropError("");
  }, []);
  const reset = useCallback(() => {
    generation.current.reset(); if (timer.current) clearTimeout(timer.current); timer.current = null;
    clearCrop(); setState(null); setResponse(null); setError(""); setBusy(false); setChosen(null);
  }, [clearCrop]);
  function failure(e: unknown) {
    if (e instanceof ApiError && [401,403,404,409].includes(e.status)) handleError.current(e);
    else setError("证据定位暂时不可用，原图仍可阅读。请重试。");
  }
  async function status(stamp: number) {
    if (!selected || !index) return;
    const req=PagesService.getRegionStatus(selected.page_id), release=generation.current.track(() => req.cancel());
    const timeout=setTimeout(() => req.cancel(),15_000);
    try {
      const next=await req;
      if (!generation.current.accepts(stamp)) return;
      if (!matchesRegionPage(next,selected,index)) throw new Error("Region identity mismatch");
      setState(next);setError("");
      if (next.status === "running" || next.status === "queued") {
        if (Date.now()<deadline.current) timer.current=setTimeout(() => void status(stamp),2500);
        else setError("解析仍在服务端运行，已暂停轮询。请手动刷新状态。");
      }
    } catch(e) { if (generation.current.accepts(stamp)) failure(e); }
    finally {clearTimeout(timeout);release();if(generation.current.accepts(stamp))setBusy(false);}
  }
  useEffect(() => {
    reset();if (!enabled || !selected || !index) return;
    deadline.current=Date.now()+600_000;void status(generation.current.current());
    return reset;
    // This scope owns independent cancelation; query text edits cannot substitute submitted Q.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled,selected?.page_id,selected?.render_sha256,selected?.document_version_id,index,question,reset]);
  async function locate() {
    if (!selected || !index || !question || busy) return;
    const stamp=generation.current.reset();if(timer.current)clearTimeout(timer.current);
    clearCrop();setResponse(null);setChosen(null);setBusy(true);setError("");
    const req=PagesService.rankPageRegions(selected.page_id,{q:question,document_version_id:selected.document_version_id,
      render_sha256:selected.render_sha256,index_generation:index});
    const release=generation.current.track(() => req.cancel()), timeout=setTimeout(() => req.cancel(),235_000);
    try {
      const next=await req;
      if(!generation.current.accepts(stamp))return;
      if(!matchesRegionPage(next,selected,index))throw new Error("Region identity mismatch");
      setState(next);
      if(next.status==='ready') {
        if(!validRegions(next))throw new Error("Invalid regions");
        setResponse(next);setChosen(next.items[0].layout_id);
      }
    }catch(e){if(generation.current.accepts(stamp))failure(e);}
    finally{clearTimeout(timeout);release();if(generation.current.accepts(stamp))setBusy(false);}
  }
  async function parse() {
    if (!selected || !state?.can_parse || busy) return;
    const stamp=generation.current.reset();clearCrop();setResponse(null);setBusy(true);setError("");
    const retry=['failed','timeout','interrupted'].includes(state.status) && state.task_id ? state.task_id : undefined;
    const req=DocumentsService.requestDocumentParsing(selected.document_id,{retry_task_id:retry});
    const release=generation.current.track(() => req.cancel()),timeout=setTimeout(() => req.cancel(),15_000);
    try{await req;if(generation.current.accepts(stamp)){deadline.current=Date.now()+600_000;void status(stamp);}}
    catch(e){if(generation.current.accepts(stamp))failure(e);}
    finally{clearTimeout(timeout);release();if(generation.current.accepts(stamp))setBusy(false);}
  }
  async function previewCrop(item:RegionItem) {
    clearCrop();setCropBusy(true);setChosen(item.layout_id);
    const stamp=cropGeneration.current.current(),scope=generation.current.current(),controller=new AbortController();
    const release=cropGeneration.current.track(() => controller.abort()),timeout=setTimeout(() => controller.abort(),15_000);
    try{
      const result=await fetch(privateCropPath(item.crop_url),{credentials:'same-origin',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',signal:controller.signal});
      if(!generation.current.accepts(scope)||!cropGeneration.current.accepts(stamp))return;
      if([401,403,404,409].includes(result.status)) {
        // Reuse the actual SDK error handling for permission/session transitions.
        handleError.current(new ApiError({method:'GET',url:item.crop_url},{url:item.crop_url,ok:false,status:result.status,statusText:result.statusText,body:{detail:result.status===403?'PASSWORD_CHANGE_REQUIRED':'REGION_NOT_FOUND'}},'Crop unavailable'));return;
      }
      if(!result.ok||result.headers.get('content-type')?.split(';',1)[0]!=='image/png')throw new Error('Invalid crop');
      const blob=await result.blob();if(!generation.current.accepts(scope)||!cropGeneration.current.accepts(stamp))return;
      cropUrl.current=URL.createObjectURL(blob);setCrop(cropUrl.current);
    }catch{if(generation.current.accepts(scope)&&cropGeneration.current.accepts(stamp))setCropError('裁剪暂时无法加载，原图仍可阅读。');}
    finally{clearTimeout(timeout);release();if(cropGeneration.current.accepts(stamp))setCropBusy(false);}
  }
  return {reset,panel:{state,response,busy,error,crop,cropBusy,cropError,chosen,onLocate:()=>void locate(),onParse:()=>void parse(),
    onRefresh:()=>{reset();deadline.current=Date.now()+600_000;void status(generation.current.current());},
    onChoose:(item:RegionItem)=>{clearCrop();setChosen(item.layout_id);},onCrop:(item:RegionItem)=>void previewCrop(item)}};
}
export type RegionsProps=ReturnType<typeof useRegions>['panel'];
