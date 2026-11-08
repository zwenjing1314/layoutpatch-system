/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegionItem } from './RegionItem';
export type RegionResponse = {
    document_id: string;
    document_version_id: string;
    page_id: string;
    page_number: number;
    render_sha256: string;
    width_px: number;
    height_px: number;
    index_generation: string;
    status: 'not_requested' | 'queued' | 'running' | 'ready' | 'no_candidates' | 'failed' | 'timeout' | 'interrupted' | 'unavailable';
    can_parse: boolean;
    task_id?: (string | null);
    candidate_hash?: (string | null);
    parser_profile_sha256?: (string | null);
    model_profile_sha256: string;
    error_code?: (string | null);
    query_sha256?: (string | null);
    items: Array<RegionItem>;
};

