/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LoginInput } from '../models/LoginInput';
import type { MeResponse } from '../models/MeResponse';
import type { PasswordInput } from '../models/PasswordInput';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuthService {
    /**
     * Login
     * @param requestBody
     * @returns MeResponse Successful Response
     * @throws ApiError
     */
    public static login(
        requestBody: LoginInput,
    ): CancelablePromise<MeResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/login',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Me
     * @returns MeResponse Successful Response
     * @throws ApiError
     */
    public static getMe(): CancelablePromise<MeResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/auth/me',
        });
    }
    /**
     * Logout
     * @returns void
     * @throws ApiError
     */
    public static logout(): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/logout',
        });
    }
    /**
     * Password
     * @param requestBody
     * @returns void
     * @throws ApiError
     */
    public static changePassword(
        requestBody: PasswordInput,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/password',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
