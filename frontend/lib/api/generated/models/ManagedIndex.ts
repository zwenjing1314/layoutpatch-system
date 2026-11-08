/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ManagedIndex = {
    index_id: string;
    profile_id: string;
    status: 'pending' | 'building' | 'ready' | 'failed';
    page_count: number;
    vector_count: number;
    feature_sha256: (string | null);
    manifest_sha256: (string | null);
    created_at: string;
};

