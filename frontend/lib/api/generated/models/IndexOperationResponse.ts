/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { IndexMetrics } from './IndexMetrics';
export type IndexOperationResponse = {
    operation_id: string;
    kind: 'verify' | 'rebuild' | 'activate';
    status: 'running' | 'completed' | 'failed' | 'interrupted';
    source_id: string;
    target_id: string;
    expected_epoch: number;
    error_code: (string | null);
    metrics: IndexMetrics;
    created_at: string;
    updated_at: string;
};

