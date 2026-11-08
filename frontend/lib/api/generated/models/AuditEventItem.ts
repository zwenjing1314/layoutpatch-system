/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AuditEventItem = {
    event_id: string;
    category: 'account' | 'sharing' | 'deletion' | 'history' | 'index';
    actor_id: (string | null);
    target_id: (string | null);
    actor_type: 'user' | 'cli' | 'system';
    action: string;
    outcome: 'success' | 'noop' | 'rejected' | 'failed' | 'started';
    code: string;
    occurred_at: number;
};

