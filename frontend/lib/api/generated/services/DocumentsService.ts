/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocumentListResponse } from '../models/DocumentListResponse';
import type { DocumentResponse } from '../models/DocumentResponse';
import type { JobActionInput } from '../models/JobActionInput';
import type { JobListResponse } from '../models/JobListResponse';
import type { JobResponse } from '../models/JobResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DocumentsService {
    /**
     * Get Job
     * @param jobId
     * @returns JobResponse Successful Response
     * @throws ApiError
     */
    public static getJob(
        jobId: string,
    ): CancelablePromise<JobResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/jobs/{job_id}',
            path: {
                'job_id': jobId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Document
     * @param documentId
     * @returns DocumentResponse Successful Response
     * @throws ApiError
     */
    public static getDocument(
        documentId: string,
    ): CancelablePromise<DocumentResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/documents/{document_id}',
            path: {
                'document_id': documentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Upload Pdf
     * @param xUploadId
     * @param xCsrfToken
     * @param formData
     * @returns JobResponse Successful Response
     * @throws ApiError
     */
    public static uploadPdf(
        xUploadId: string,
        xCsrfToken: string,
        formData: {
            file: Blob;
        },
    ): CancelablePromise<JobResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/index',
            headers: {
                'X-Upload-ID': xUploadId,
                'X-CSRF-Token': xCsrfToken,
            },
            formData: formData,
            mediaType: 'multipart/form-data',
        });
    }
    /**
     * List Documents
     * @param name
     * @param limit
     * @param cursor
     * @returns DocumentListResponse Successful Response
     * @throws ApiError
     */
    public static listDocuments(
        name: string = '',
        limit: number = 20,
        cursor?: (string | null),
    ): CancelablePromise<DocumentListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/documents',
            query: {
                'name': name,
                'limit': limit,
                'cursor': cursor,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Jobs
     * @param limit
     * @param cursor
     * @returns JobListResponse Successful Response
     * @throws ApiError
     */
    public static listJobs(
        limit: number = 10,
        cursor?: (string | null),
    ): CancelablePromise<JobListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/jobs',
            query: {
                'limit': limit,
                'cursor': cursor,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Retry Job
     * @param jobId
     * @param requestBody
     * @returns JobResponse Successful Response
     * @throws ApiError
     */
    public static retryJob(
        jobId: string,
        requestBody: JobActionInput,
    ): CancelablePromise<JobResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/jobs/{job_id}/retry',
            path: {
                'job_id': jobId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Cancel Job
     * @param jobId
     * @param requestBody
     * @returns JobResponse Successful Response
     * @throws ApiError
     */
    public static cancelJob(
        jobId: string,
        requestBody: JobActionInput,
    ): CancelablePromise<JobResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/jobs/{job_id}/cancel',
            path: {
                'job_id': jobId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
