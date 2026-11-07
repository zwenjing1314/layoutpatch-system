/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DocumentResponse } from '../models/DocumentResponse';
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
}
