/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { IndexCommand } from '../models/IndexCommand';
import type { IndexManagementState } from '../models/IndexManagementState';
import type { IndexOperationResponse } from '../models/IndexOperationResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class IndexesService {
    /**
     * State
     * @param offset
     * @param operationOffset
     * @returns IndexManagementState Successful Response
     * @throws ApiError
     */
    public static getIndexManagement(
        offset?: number,
        operationOffset?: number,
    ): CancelablePromise<IndexManagementState> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/index-management',
            query: {
                'offset': offset,
                'operation_offset': operationOffset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Verify
     * @param requestBody
     * @returns IndexOperationResponse Successful Response
     * @throws ApiError
     */
    public static verifyIndexProfile(
        requestBody: IndexCommand,
    ): CancelablePromise<IndexOperationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/index-management/verify',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Rebuild
     * @param requestBody
     * @returns IndexOperationResponse Successful Response
     * @throws ApiError
     */
    public static rebuildIndex(
        requestBody: IndexCommand,
    ): CancelablePromise<IndexOperationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/index-management/rebuild',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Activate
     * @param requestBody
     * @returns IndexOperationResponse Successful Response
     * @throws ApiError
     */
    public static activateIndex(
        requestBody: IndexCommand,
    ): CancelablePromise<IndexOperationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/index-management/activate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
