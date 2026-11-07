/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DocumentListItem = {
    document_id: string;
    display_name: string;
    document_version_id: (string | null);
    version: (number | null);
    page_count: (number | null);
    visibility: 'private' | 'shared';
    access: 'own' | 'shared';
    status: string;
    job_status: (string | null);
    error_code: (string | null);
    created_at: string;
    searchable: boolean;
    unsearchable_reason: ('DOCUMENT_NOT_READY' | 'METADATA_INCOMPLETE' | 'INDEX_UNAVAILABLE' | 'INDEX_INCOMPLETE' | null);
};

