/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SharingInput } from '../models/SharingInput';
import type { SharingList } from '../models/SharingList';
import type { SharingMutation } from '../models/SharingMutation';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SharingService {
    /**
     * Listing
     * @param name
     * @param limit
     * @param offset
     * @returns SharingList Successful Response
     * @throws ApiError
     */
    public static listSharingDocuments(
        name: string = '',
        limit: number = 10,
        offset?: number,
    ): CancelablePromise<SharingList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/documents',
            query: {
                'name': name,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Publish
     * @param documentId
     * @param requestBody
     * @returns SharingMutation Successful Response
     * @throws ApiError
     */
    public static publishDocument(
        documentId: string,
        requestBody: SharingInput,
    ): CancelablePromise<SharingMutation> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/documents/{document_id}/publish',
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
     * Unpublish
     * @param documentId
     * @param requestBody
     * @returns SharingMutation Successful Response
     * @throws ApiError
     */
    public static unpublishDocument(
        documentId: string,
        requestBody: SharingInput,
    ): CancelablePromise<SharingMutation> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/documents/{document_id}/unpublish',
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
