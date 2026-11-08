/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PageParseStatus = {
    page_id: string;
    page_index: number;
    page_number: number;
    render_sha256: string;
    width_px: number;
    height_px: number;
    status: 'pending' | 'running' | 'ready' | 'no_candidates' | 'failed' | 'timeout' | 'interrupted';
    candidate_count: number;
    candidate_hash: (string | null);
    error_code: (string | null);
};

