/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobAttemptResponse } from './JobAttemptResponse';
export type JobResponse = {
    job_id: string;
    document_id: string;
    document_version_id: string;
    kind: string;
    stage: string;
    status: string;
    progress: number;
    attempt: number;
    error_code: (string | null);
    created_at: string;
    updated_at: string;
    retry_available?: boolean;
    cancel_available: boolean;
    cancel_requested_at: (string | null);
    display_name: string;
    page_count: number;
    attempts: Array<JobAttemptResponse>;
};

