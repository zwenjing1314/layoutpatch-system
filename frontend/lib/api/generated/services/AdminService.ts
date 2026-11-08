/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountActive } from '../models/AccountActive';
import type { AccountCreate } from '../models/AccountCreate';
import type { AccountList } from '../models/AccountList';
import type { AccountMutation } from '../models/AccountMutation';
import type { AccountReset } from '../models/AccountReset';
import type { AccountRevoke } from '../models/AccountRevoke';
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
    /**
     * List Accounts
     * @param limit
     * @param offset
     * @returns AccountList Successful Response
     * @throws ApiError
     */
    public static listAccounts(
        limit: number = 50,
        offset?: number,
    ): CancelablePromise<AccountList> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/admin/users',
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
     * Create
     * @param requestBody
     * @returns AccountMutation Successful Response
     * @throws ApiError
     */
    public static createAccount(
        requestBody: AccountCreate,
    ): CancelablePromise<AccountMutation> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/users',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Active
     * @param userId
     * @param requestBody
     * @returns AccountMutation Successful Response
     * @throws ApiError
     */
    public static setAccountActive(
        userId: string,
        requestBody: AccountActive,
    ): CancelablePromise<AccountMutation> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/admin/users/{user_id}',
            path: {
                'user_id': userId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Reset
     * @param userId
     * @param requestBody
     * @returns AccountMutation Successful Response
     * @throws ApiError
     */
    public static resetAccountPassword(
        userId: string,
        requestBody: AccountReset,
    ): CancelablePromise<AccountMutation> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/users/{user_id}/password',
            path: {
                'user_id': userId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Revoke
     * @param userId
     * @param requestBody
     * @returns AccountMutation Successful Response
     * @throws ApiError
     */
    public static revokeAccountSessions(
        userId: string,
        requestBody: AccountRevoke,
    ): CancelablePromise<AccountMutation> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/admin/users/{user_id}/sessions/revoke',
            path: {
                'user_id': userId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
