/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type JobAttemptResponse = {
    attempt: number;
    status: string;
    stage: string;
    progress: number;
    error_code: (string | null);
    cancel_requested_at: (string | null);
    created_at: string;
    updated_at: string;
    started_at: (string | null);
    ended_at: (string | null);
};

