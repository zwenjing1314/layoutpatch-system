"""Authorized literal name filtering and session-bound snapshot pagination."""
import base64
import hashlib
import hmac
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.auth.routes import load_cookie, principal
from backend.db.models import Document, DocumentVersion, IndexPage, Job, Page, User
from backend.db.seed import canonical, sha
from backend.search.qdrant import SearchUnavailable
from backend.search.scope import active_index
from .access import visible_document
from .names import normalize_name

router = APIRouter(dependencies=[Depends(load_cookie)])


class DocumentListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=255)
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class DocumentListItem(BaseModel):
    document_id: str
    display_name: str
    document_version_id: str | None
    version: int | None
    page_count: int | None
    visibility: Literal["private", "shared"]
    access: Literal["own", "shared"]
    status: str
    job_status: str | None
    error_code: str | None
    created_at: str
    searchable: bool
    unsearchable_reason: Literal["DOCUMENT_NOT_READY", "METADATA_INCOMPLETE", "INDEX_UNAVAILABLE", "INDEX_INCOMPLETE"] | None


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    next_cursor: str | None
    scope_version: str


def list_snapshot(db, user, name_key):
    latest = (select(DocumentVersion.id).where(DocumentVersion.document_id == Document.id)
              .order_by(DocumentVersion.version.desc()).limit(1).correlate(Document).scalar_subquery())
    chosen = case((Document.status == "ready", Document.active_version_id), else_=latest)
    rows = db.execute(select(Document, DocumentVersion, Job).join(User, User.id == Document.owner_id)
                      .outerjoin(DocumentVersion, (DocumentVersion.id == chosen) & (DocumentVersion.document_id == Document.id))
                      .outerjoin(Job, Job.document_version_id == DocumentVersion.id)
                      .where(visible_document(user), func.instr(Document.display_name_key, name_key) > 0)
                      .order_by(Document.created_at.desc(), Document.id.desc())).all()
    try:
        index, _ = active_index(db)
        index_id = index.id
    except SearchUnavailable:
        index_id = None
    indexed = {}
    if index_id:
        versions = [version.id for doc, version, _ in rows if version and doc.status == "ready"]
        for version_id, page_index in db.execute(select(Page.document_version_id, Page.page_index).join(IndexPage, IndexPage.page_id == Page.id)
                                                .where(IndexPage.index_id == index_id, Page.document_version_id.in_(versions))):
            indexed.setdefault(version_id, []).append(page_index)
    items = []
    for doc, version, job in rows:
        own = doc.owner_id == user.id
        reason = None
        if not version:
            reason = "METADATA_INCOMPLETE"
        elif doc.status != "ready" or doc.active_version_id != version.id:
            reason = "DOCUMENT_NOT_READY"
        elif index_id is None:
            reason = "INDEX_UNAVAILABLE"
        elif sorted(indexed.get(version.id, [])) != list(range(version.page_count)):
            reason = "INDEX_INCOMPLETE"
        items.append(DocumentListItem(document_id=doc.id, display_name=doc.display_name,
            document_version_id=version.id if version else None, version=version.version if version else None,
            page_count=version.page_count if version else None, visibility=doc.visibility,
            access="own" if own else "shared", status=doc.status, job_status=job.status if own and job else None,
            error_code=job.error_code if own and job else None, created_at=doc.created_at,
            searchable=reason is None, unsearchable_reason=reason))
    identity = (user.id, user.role, user.auth_version)
    fingerprint = sha(canonical({"identity": identity, "index": index_id, "items": [i.model_dump() for i in items]}).encode())
    return items, fingerprint


def encode_cursor(data, csrf_token):
    raw = canonical(data).encode()
    signature = hmac.new(csrf_token.encode(), b"document-list-v1\0" + raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + signature).decode().rstrip("=")


def decode_cursor(value, csrf_token):
    try:
        packed = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        raw, signature = packed[:-32], packed[-32:]
        expected = hmac.new(csrf_token.encode(), b"document-list-v1\0" + raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"v", "name", "limit", "scope", "after"} or data["v"] != 1:
            raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(422, "INVALID_CURSOR") from None


@router.get("/documents", response_model=DocumentListResponse, operation_id="list_documents", tags=["documents"])
def list_documents(request: Request, params: Annotated[DocumentListInput, Query()]):
    if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise HTTPException(422, "INVALID_REQUEST")
    name_key = normalize_name(params.name.strip())
    name_digest = sha(name_key.encode())
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db, require_changed=True)
        items, fingerprint = list_snapshot(db, user, name_key)
        offset = 0
        if params.cursor:
            cursor = decode_cursor(params.cursor, row.csrf_token)
            if cursor["name"] != name_digest or cursor["limit"] != params.limit:
                raise HTTPException(422, "INVALID_CURSOR")
            if cursor["scope"] != fingerprint:
                raise HTTPException(409, "DOCUMENT_LIST_CHANGED")
            positions = [n for n, item in enumerate(items) if item.document_id == cursor["after"]]
            if len(positions) != 1:
                raise HTTPException(422, "INVALID_CURSOR")
            offset = positions[0] + 1
        selected = items[offset:offset + params.limit]
        next_cursor = None
        if offset + params.limit < len(items):
            next_cursor = encode_cursor({"v": 1, "name": name_digest, "limit": params.limit,
                                         "scope": fingerprint, "after": selected[-1].document_id}, row.csrf_token)
    # A fresh transaction must observe authority changes, including during list construction.
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        if list_snapshot(db, user, name_key)[1] != fingerprint:
            raise HTTPException(409, "DOCUMENT_LIST_CHANGED")
    return DocumentListResponse(items=selected, next_cursor=next_cursor, scope_version=fingerprint)
