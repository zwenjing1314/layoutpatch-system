/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SearchHit } from './SearchHit';
export type SearchResponse = {
    status: 'ok' | 'empty';
    search_mode: 'library' | 'document';
    document_id: (string | null);
    profile_id: string;
    index_generation: string;
    scope_version: string;
    timings_ms: Record<string, number>;
    items: Array<SearchHit>;
};

