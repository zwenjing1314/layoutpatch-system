/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { IndexOperationResponse } from './IndexOperationResponse';
import type { ManagedIndex } from './ManagedIndex';
import type { ManagedProfile } from './ManagedProfile';
export type IndexManagementState = {
    active_index_id: string;
    index_epoch: number;
    profiles: Array<ManagedProfile>;
    indexes: Array<ManagedIndex>;
    next_offset: (number | null);
    operations: Array<IndexOperationResponse>;
    next_operation_offset: (number | null);
};

