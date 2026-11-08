import type { RegionResponse, RegionState, SearchHit } from "./api/generated";

export function inferenceFailed(state: RegionState | null) {
  return state?.status === 'failed' && ['REGION_INFERENCE_FAILED', 'MODEL_BUSY'].includes(state.error_code ?? '');
}

export function matchesRegionPage(state: RegionState, hit: SearchHit, index: string) {
  return state.page_id === hit.page_id && state.document_id === hit.document_id && state.document_version_id === hit.document_version_id
    && state.render_sha256 === hit.render_sha256 && state.width_px === hit.width_px && state.height_px === hit.height_px
    && state.page_number === hit.page_number && state.index_generation === index;
}
export function validRegions(response: RegionResponse) {
  const ids = new Set<string>();
  return response.status === "ready" && response.items.length > 0 && response.items.every((r, i) => {
    const [x1,y1,x2,y2] = r.bbox;
    const valid = !ids.has(r.candidate_id) && r.candidate_id === `${response.page_id}:block:${r.layout_id}` && r.rank === i+1
      && Number.isFinite(r.score) && r.bbox.every(Number.isFinite) && x1 >= 0 && y1 >= 0 && x2 > x1 && y2 > y1
      && x2 <= response.width_px && y2 <= response.height_px;
    ids.add(r.candidate_id); return valid;
  });
}
export function privateCropPath(url: string) {
  if (!/^\/pages\/[0-9a-f-]{36}\/regions\/\d+\/crop\?task=[0-9a-f-]{36}&candidate_hash=[0-9a-f]{64}&model=[0-9a-f]{64}&token=[0-9a-f]{64}$/.test(url)) throw new Error("Invalid crop URL");
  return `/api${url}`;
}
