import math
import time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.auth.routes import load_cookie, principal
from backend.documents.previews import preview_url
from .qdrant import SearchUnavailable
from .scope import allowed_scope
from .worker import SearchBusy

router = APIRouter()


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    q: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=3, ge=1, le=50)
    document_id: UUID | None = None


class SearchHit(BaseModel):
    document_id: str
    document_version_id: str
    page_id: str
    page_index: int
    page_number: int
    document_name: str
    page_rank: int
    page_score: float
    width_px: int
    height_px: int
    render_sha256: str
    preview_url: str
    region_status: Literal["not_requested"] = "not_requested"


class SearchResponse(BaseModel):
    status: Literal["ok", "empty"]
    search_mode: Literal["library", "document"]
    document_id: str | None
    profile_id: str
    index_generation: str
    scope_version: str
    timings_ms: dict[str, float]
    items: list[SearchHit]


@router.get("/search", response_model=SearchResponse, operation_id="search_pages", tags=["search"],
            dependencies=[Depends(load_cookie)])
def search(request: Request, params: Annotated[SearchInput, Query()]):
    start = time.perf_counter()
    document_id = str(params.document_id) if params.document_id is not None else None
    mode = "document" if document_id is not None else "library"
    if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise HTTPException(422, "INVALID_REQUEST")
    try:
        with Session(request.app.state.engine) as db:
            _, user = principal(request, db, require_changed=True)
            identity = (user.id, user.role, user.auth_version)
            scope = allowed_scope(db, user, document_id)
        if not scope.pages:
            # No model startup and no Qdrant call for empty authorized scope.
            return SearchResponse(status="empty", search_mode=mode, document_id=document_id, profile_id=scope.profile_id, index_generation=scope.index_id,
                                  scope_version=scope.fingerprint, timings_ms={"total": (time.perf_counter()-start)*1000}, items=[])
        tick = time.perf_counter()
        vector = request.app.state.model_worker.encode(params.q, scope.encoder_sha256)
        encode_ms = (time.perf_counter()-tick)*1000
        tick = time.perf_counter()
        hits = request.app.state.qdrant.query(scope, vector, params.k)
        search_ms = (time.perf_counter()-tick)*1000
        if len(hits) != min(params.k, len(scope.pages)):
            raise SearchUnavailable("Incomplete index response")
        pages, seen, result = {p.id: p for p in scope.pages}, set(), []
        for hit in hits:
            if not isinstance(hit, dict):
                raise SearchUnavailable("Invalid hit")
            page = pages.get(str(hit.get("id")))
            payload = hit.get("payload", {})
            if page is None or page.id in seen or not isinstance(payload, dict):
                raise SearchUnavailable("Unexpected hit")
            expected = {"page_id": page.id, "document_id": page.document_id, "document_version_id": page.version_id,
                        "profile_id": scope.profile_id, "index_generation": scope.index_id,
                        "render_sha256": page.render_sha256, "embedding_sha256": page.embedding_sha256}
            score = hit.get("score")
            if any(payload.get(k) != v for k, v in expected.items()) or type(score) not in (int, float) or not math.isfinite(score):
                raise SearchUnavailable("Invalid hit identity/score")
            seen.add(page.id)
            result.append((page, float(score)))
        # Release the earlier read transaction before inference, then reread all
        # authority, including scope changes that could have affected Top-k.
        with Session(request.app.state.engine) as db:
            row, user = principal(request, db, require_changed=True)
            try:
                current = allowed_scope(db, user, document_id)
            except HTTPException as exc:
                if exc.status_code in (404, 409):
                    raise HTTPException(409, "SEARCH_SCOPE_CHANGED") from None
                raise
            if identity != (user.id, user.role, user.auth_version) or current != scope:
                raise HTTPException(409, "SEARCH_SCOPE_CHANGED")
        result.sort(key=lambda item: (-item[1], item[0].id))
        items = [SearchHit(document_id=p.document_id, document_version_id=p.version_id, page_id=p.id,
                           page_index=p.page_index, page_number=p.page_index+1, document_name=p.document_name,
                           page_rank=rank+1, page_score=score, width_px=p.width_px, height_px=p.height_px,
                           render_sha256=p.render_sha256, preview_url=preview_url(row, p.id, p.render_sha256))
                 for rank, (p, score) in enumerate(result)]
        return SearchResponse(status="ok", search_mode=mode, document_id=document_id, profile_id=scope.profile_id, index_generation=scope.index_id,
                              scope_version=scope.fingerprint, timings_ms={"query_encode_including_queue": encode_ms,
                              "page_search": search_ms, "total": (time.perf_counter()-start)*1000}, items=items)
    except SearchBusy:
        raise HTTPException(503, "MODEL_BUSY", headers={"Retry-After": "5"}) from None
    except SearchUnavailable:
        raise HTTPException(503, "SEARCH_UNAVAILABLE") from None
