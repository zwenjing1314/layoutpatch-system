/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegionInput } from '../models/RegionInput';
import type { RegionResponse } from '../models/RegionResponse';
import type { RegionState } from '../models/RegionState';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PagesService {
    /**
     * Page Image
     * @param pageId
     * @param preview
     * @returns binary Successful Response
     * @throws ApiError
     */
    public static getPageImage(
        pageId: string,
        preview?: (string | null),
    ): CancelablePromise<Blob> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/pages/{page_id}/image',
            path: {
                'page_id': pageId,
            },
            query: {
                'preview': preview,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Status
     * @param pageId
     * @returns RegionState Successful Response
     * @throws ApiError
     */
    public static getRegionStatus(
        pageId: string,
    ): CancelablePromise<RegionState> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/pages/{page_id}/regions/status',
            path: {
                'page_id': pageId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Rank Page
     * @param pageId
     * @param requestBody
     * @returns RegionResponse Successful Response
     * @throws ApiError
     */
    public static rankPageRegions(
        pageId: string,
        requestBody: RegionInput,
    ): CancelablePromise<RegionResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/pages/{page_id}/regions',
            path: {
                'page_id': pageId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Crop
     * @param pageId
     * @param layoutId
     * @param task
     * @param candidateHash
     * @param model
     * @param token
     * @returns binary Successful Response
     * @throws ApiError
     */
    public static getRegionCrop(
        pageId: string,
        layoutId: number,
        task: string = '',
        candidateHash: string = '',
        model: string = '',
        token: string = '',
    ): CancelablePromise<Blob> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/pages/{page_id}/regions/{layout_id}/crop',
            path: {
                'page_id': pageId,
                'layout_id': layoutId,
            },
            query: {
                'task': task,
                'candidate_hash': candidateHash,
                'model': model,
                'token': token,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
