from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.admin import authorize
from backend.auth.routes import load_cookie, principal
from backend.db.models import IndexGeneration, IndexOperation, PipelineProfile
from backend.search.qdrant import SearchUnavailable
from backend.search.scope import active_index, index_epoch, profile_identity
from .service import manage, operation_view

router = APIRouter(prefix="/admin/index-management", tags=["indexes"], dependencies=[Depends(load_cookie)])


class IndexMetrics(BaseModel):
    encoder_sha256: str | None = None
    verified_files: int | None = None
    implementation_count: int | None = None
    network_attempts: int | None = None
    inference_count: int | None = None
    elapsed_ms: float | None = None
    page_count: int | None = None
    vector_count: int | None = None
    full_bf16_bytes: int | None = None
    vector_float32_bytes: int | None = None
    page_encoding_count: int | None = None
    storage_basis: str | None = None


class IndexOperationResponse(BaseModel):
    operation_id: str
    kind: Literal["verify", "rebuild", "activate"]
    status: Literal["running", "completed", "failed", "interrupted"]
    source_id: str
    target_id: str
    expected_epoch: int
    error_code: str | None
    metrics: IndexMetrics
    created_at: str
    updated_at: str


class ManagedIndex(BaseModel):
    index_id: str
    profile_id: str
    status: Literal["pending", "building", "ready", "failed"]
    page_count: int
    vector_count: int
    feature_sha256: str | None
    manifest_sha256: str | None
    created_at: str


class ManagedProfile(BaseModel):
    profile_id: str
    name: str
    config_sha256: str
    status: str
    identity_matches: bool
    encoder_sha256: str | None


class IndexManagementState(BaseModel):
    active_index_id: str
    index_epoch: int
    profiles: list[ManagedProfile]
    indexes: list[ManagedIndex]
    next_offset: int | None
    operations: list[IndexOperationResponse]
    next_operation_offset: int | None


class IndexCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    index_id: UUID
    active_index_id: UUID
    index_epoch: int = Field(ge=1, strict=True)
    confirmed: StrictBool


@router.get("", response_model=IndexManagementState, operation_id="get_index_management")
def state(request: Request, offset: int = Query(0, ge=0, le=1000000), operation_offset: int = Query(0, ge=0, le=1000000)):
    if any(k not in ("offset", "operation_offset") or len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, "INVALID_REQUEST")
    def snapshot(db):
        principal(request, db, require_changed=True, admin=True)
        try:
            current, _ = active_index(db)
        except SearchUnavailable:
            raise HTTPException(503, "ACTIVE_INDEX_UNAVAILABLE") from None
        profiles = []
        for p in db.scalars(select(PipelineProfile).order_by(PipelineProfile.name)):
            try:
                encoder = profile_identity(p)
            except SearchUnavailable:
                encoder = None
            profiles.append(ManagedProfile(profile_id=p.id, name=p.name, config_sha256=p.config_sha256,
                status=p.status, identity_matches=encoder is not None, encoder_sha256=encoder))
        rows = list(db.scalars(select(IndexGeneration).order_by(IndexGeneration.created_at.desc(), IndexGeneration.id).offset(offset).limit(11)))
        operations = list(db.scalars(select(IndexOperation).order_by(IndexOperation.created_at.desc(), IndexOperation.id).offset(operation_offset).limit(11)))
        return IndexManagementState(active_index_id=current.id, index_epoch=index_epoch(db), profiles=profiles,
            indexes=[ManagedIndex(index_id=r.id, profile_id=r.profile_id, status=r.status, page_count=r.page_count,
                vector_count=r.vector_count, feature_sha256=r.feature_file_sha256, manifest_sha256=r.source_manifest_sha256,
                created_at=r.created_at) for r in rows[:10]], next_offset=offset+10 if len(rows)>10 else None,
            operations=[IndexOperationResponse(**operation_view(r)) for r in operations[:10]],
            next_operation_offset=operation_offset+10 if len(operations)>10 else None)
    with Session(request.app.state.engine) as db:
        first = snapshot(db)
    with Session(request.app.state.engine) as db:
        second = snapshot(db)
    if first != second:
        raise HTTPException(409, "INDEX_LIST_CHANGED")
    return second


def invoke(request, body, kind):
    if request.query_params or not body.confirmed:
        raise HTTPException(422, "CONFIRMATION_REQUIRED")
    try:
        return manage(request.app.state.engine, request.app.state.qdrant, kind, body,
            authorize(request), request.app.state.clock)
    except SearchUnavailable:
        raise HTTPException(503, "INDEX_VERIFICATION_FAILED") from None


@router.post("/verify", response_model=IndexOperationResponse, operation_id="verify_index_profile")
def verify(body: IndexCommand, request: Request):
    return invoke(request, body, "verify")


@router.post("/rebuild", response_model=IndexOperationResponse, operation_id="rebuild_index")
def rebuild(body: IndexCommand, request: Request):
    return invoke(request, body, "rebuild")


@router.post("/activate", response_model=IndexOperationResponse, operation_id="activate_index")
def activate(body: IndexCommand, request: Request):
    return invoke(request, body, "activate")
