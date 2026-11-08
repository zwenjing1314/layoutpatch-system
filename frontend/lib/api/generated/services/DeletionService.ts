/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CleanupRetryInput } from '../models/CleanupRetryInput';
import type { DeletionDocument } from '../models/DeletionDocument';
import type { DeletionInput } from '../models/DeletionInput';
import type { DeletionList } from '../models/DeletionList';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DeletionService {
    /**
     * Listing
     * @param limit
     * @param offset
     * @returns DeletionList Successful Response
     * @throws ApiError
     */
    public static listDeletionDocuments(
        limit: number = 10,
        offset?: number,
    ): CancelablePromise<DeletionList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/documents/deletion',
            query: {
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Own
     * @param documentId
     * @param requestBody
     * @returns DeletionDocument Successful Response
     * @throws ApiError
     */
    public static deleteOwnDocument(
        documentId: string,
        requestBody: DeletionInput,
    ): CancelablePromise<DeletionDocument> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/documents/{document_id}/delete',
            path: {
                'document_id': documentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Status
     * @param documentId
     * @returns DeletionDocument Successful Response
     * @throws ApiError
     */
    public static getDocumentCleanup(
        documentId: string,
    ): CancelablePromise<DeletionDocument> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/documents/{document_id}/cleanup',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Retry
     * @param documentId
     * @param requestBody
     * @returns DeletionDocument Successful Response
     * @throws ApiError
     */
    public static retryDocumentCleanup(
        documentId: string,
        requestBody: CleanupRetryInput,
    ): CancelablePromise<DeletionDocument> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/documents/{document_id}/cleanup/retry',
            path: {
                'document_id': documentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
