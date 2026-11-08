/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AuditTaskItem = {
    task_id: string;
    kind: 'ingest' | 'parsing' | 'cleanup' | 'search' | 'index';
    owner_id: string;
    document_id: (string | null);
    status: 'receiving' | 'queued' | 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted' | 'ready' | 'partial' | 'deleted';
    stage: string;
    attempt: number;
    progress: (number | null);
    error_code: (string | null);
    created_at: (string | null);
    updated_at: (string | null);
};

