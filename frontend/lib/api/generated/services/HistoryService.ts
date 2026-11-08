/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HistoryDeleteInput } from '../models/HistoryDeleteInput';
import type { HistoryDeleteResponse } from '../models/HistoryDeleteResponse';
import type { HistoryDetail } from '../models/HistoryDetail';
import type { HistoryList } from '../models/HistoryList';
import type { HistorySearchInput } from '../models/HistorySearchInput';
import type { HistorySearchResponse } from '../models/HistorySearchResponse';
import type { HistorySummary } from '../models/HistorySummary';
import type { HistoryUpdateInput } from '../models/HistoryUpdateInput';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HistoryService {
    /**
     * Recorded Search
     * @param requestBody
     * @returns HistorySearchResponse Successful Response
     * @throws ApiError
     */
    public static searchAndRecordHistory(
        requestBody: HistorySearchInput,
    ): CancelablePromise<HistorySearchResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Listing
     * @param limit
     * @param offset
     * @returns HistoryList Successful Response
     * @throws ApiError
     */
    public static listQueryHistory(
        limit: number = 10,
        offset?: number,
    ): CancelablePromise<HistoryList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/history',
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
     * Get Detail
     * @param historyId
     * @returns HistoryDetail Successful Response
     * @throws ApiError
     */
    public static getQueryHistory(
        historyId: string,
    ): CancelablePromise<HistoryDetail> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/history/{history_id}',
            path: {
                'history_id': historyId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update
     * @param historyId
     * @param requestBody
     * @returns HistorySummary Successful Response
     * @throws ApiError
     */
    public static updateQueryHistory(
        historyId: string,
        requestBody: HistoryUpdateInput,
    ): CancelablePromise<HistorySummary> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/history/{history_id}',
            path: {
                'history_id': historyId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Remove
     * @param historyId
     * @param requestBody
     * @returns HistoryDeleteResponse Successful Response
     * @throws ApiError
     */
    public static deleteQueryHistory(
        historyId: string,
        requestBody: HistoryDeleteInput,
    ): CancelablePromise<HistoryDeleteResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/history/{history_id}',
            path: {
                'history_id': historyId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
