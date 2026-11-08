/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HistorySummary } from './HistorySummary';
import type { SearchHit } from './SearchHit';
export type HistoryDetail = {
    entry: HistorySummary;
    historical?: boolean;
    'q': string;
    'k': number;
    search_mode: 'library' | 'document';
    document_id: (string | null);
    target_available: (boolean | null);
    profile_id: string;
    index_generation: string;
    scope_version: string;
    current_scope_version: string;
    timings_ms: Record<string, number>;
    items: Array<SearchHit>;
    unavailable_count: number;
};

