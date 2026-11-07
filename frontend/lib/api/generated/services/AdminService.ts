/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ProfileResponse } from '../models/ProfileResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AdminService {
    /**
     * Profiles
     * @returns ProfileResponse Successful Response
     * @throws ApiError
     */
    public static getProfiles(): CancelablePromise<Array<ProfileResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/profiles',
        });
    }
}
