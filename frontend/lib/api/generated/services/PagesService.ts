/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
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
}
