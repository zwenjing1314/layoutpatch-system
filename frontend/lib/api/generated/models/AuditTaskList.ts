/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditTaskItem } from './AuditTaskItem';
export type AuditTaskList = {
    next_offset: (number | null);
    scope_version: string;
    since: number;
    until: number;
    items: Array<AuditTaskItem>;
};

