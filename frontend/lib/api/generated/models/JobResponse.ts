/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
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
};

