/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HistorySummary } from './HistorySummary';
export type HistoryList = {
    items: Array<HistorySummary>;
    next_offset: (number | null);
    scope_version: string;
    limit_per_user: number;
};

