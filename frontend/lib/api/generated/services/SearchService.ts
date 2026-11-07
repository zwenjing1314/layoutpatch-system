/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SearchResponse } from '../models/SearchResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SearchService {
    /**
     * Search
     * @param q
     * @param k
     * @returns SearchResponse Successful Response
     * @throws ApiError
     */
    public static searchPages(
        q: string,
        k: number = 3,
    ): CancelablePromise<SearchResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/search',
            query: {
                'q': q,
                'k': k,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
