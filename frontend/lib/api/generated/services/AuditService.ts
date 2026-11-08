/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditEventList } from '../models/AuditEventList';
import type { AuditTaskList } from '../models/AuditTaskList';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuditService {
    /**
     * Events
     * @param since
     * @param until
     * @param limit
     * @param offset
     * @param category
     * @param actorId
     * @param targetId
     * @param outcome
     * @returns AuditEventList Successful Response
     * @throws ApiError
     */
    public static listAuditEvents(
        since?: (number | null),
        until?: (number | null),
        limit: number = 10,
        offset?: number,
        category?: ('account' | 'sharing' | 'deletion' | 'history' | 'index' | null),
        actorId?: (string | null),
        targetId?: (string | null),
        outcome?: ('success' | 'noop' | 'rejected' | 'failed' | 'started' | null),
    ): CancelablePromise<AuditEventList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/events',
            query: {
                'since': since,
                'until': until,
                'limit': limit,
                'offset': offset,
                'category': category,
                'actor_id': actorId,
                'target_id': targetId,
                'outcome': outcome,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Tasks
     * @param since
     * @param until
     * @param limit
     * @param offset
     * @param kind
     * @param status
     * @param ownerId
     * @param documentId
     * @returns AuditTaskList Successful Response
     * @throws ApiError
     */
    public static listAuditTasks(
        since?: (number | null),
        until?: (number | null),
        limit: number = 10,
        offset?: number,
        kind?: ('ingest' | 'parsing' | 'cleanup' | 'search' | 'index' | null),
        status?: ('receiving' | 'queued' | 'running' | 'completed' | 'cancelled' | 'failed' | 'interrupted' | 'ready' | 'partial' | 'deleted' | null),
        ownerId?: (string | null),
        documentId?: (string | null),
    ): CancelablePromise<AuditTaskList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/tasks',
            query: {
                'since': since,
                'until': until,
                'limit': limit,
                'offset': offset,
                'kind': kind,
                'status': status,
                'owner_id': ownerId,
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
