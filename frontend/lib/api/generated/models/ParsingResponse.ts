/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PageParseStatus } from './PageParseStatus';
export type ParsingResponse = {
    document_id: string;
    document_version_id: (string | null);
    task_id: (string | null);
    parser_profile_id: (string | null);
    parser_profile_sha256: (string | null);
    attempt: (number | null);
    status: 'not_requested' | 'queued' | 'running' | 'ready' | 'partial' | 'failed' | 'interrupted';
    error_code: (string | null);
    pages: Array<PageParseStatus>;
};

