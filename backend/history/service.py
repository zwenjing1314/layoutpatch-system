"""Owner-only history, with write-lock authority and no model calls on reads."""
import json
import math
import unicodedata

from fastapi import HTTPException
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.auth.accounts import account_transaction
from backend.auth.routes import check_csrf, principal
from backend.db.models import HistoryEvent, QueryHistory, QueryHistoryHit, QueryRequest, now
from backend.db.seed import canonical, sha
from backend.documents.previews import preview_url
from backend.search.qdrant import SearchUnavailable
from backend.search.routes import execute_search, revalidate_search, SearchHit
from backend.search.scope import allowed_scope
from .schemas import HistoryDetail, HistorySearchResponse, HistorySummary

MAX_HISTORY = 1000  # No silent expiration/eviction; explicit owner deletion frees a slot.


def authorize(request, db, write=False):
    row, user = principal(request, db, require_changed=True)
    if write:
        check_csrf(request, row)
    return row, user


def summary(history):
    return HistorySummary(history_id=history.id, title=history.title, original_title=history.original_title,
        created_at=history.created_at, updated_at=history.updated_at, pinned_at=history.pinned_at,
        version=history.version, result_status=history.result_status, hit_count=history.hit_count)


def own(db, user, history_id):
    history = db.scalar(select(QueryHistory).where(QueryHistory.id == history_id, QueryHistory.owner_id == user.id))
    if history is None:
        raise HTTPException(404, 'HISTORY_NOT_FOUND')
    return history


def event(request, db, user, history, action, outcome='success'):
    db.add(HistoryEvent(actor_id=user.id, history_id=history.id, action=action, outcome=outcome,
                        version=history.version, occurred_at=request.app.state.clock()))


def list_snapshot(db, user):
    histories = db.scalars(select(QueryHistory).where(QueryHistory.owner_id == user.id).order_by(
        case((QueryHistory.pinned_at.is_not(None), 0), else_=1), QueryHistory.pinned_at.desc(),
        QueryHistory.created_at.desc(), QueryHistory.id.desc()))
    items = [summary(h) for h in histories]
    stamp = sha(canonical({'user': (user.id, user.role, user.auth_version), 'items': [i.model_dump() for i in items]}).encode())
    return items, stamp


def detail(request, db, user, row, history):
    # Read only current authorized pages. Never trust saved names, URLs or client hits.
    scope = allowed_scope(db, user)
    compatible = (history.profile_id, history.encoder_sha256, history.index_generation) == (scope.profile_id, scope.encoder_sha256, scope.index_id)
    pages = {p.id: p for p in scope.pages} if compatible else {}
    hits = list(db.scalars(select(QueryHistoryHit).where(QueryHistoryHit.history_id == history.id).order_by(QueryHistoryHit.page_rank)))
    if len(hits) != history.hit_count:
        raise SearchUnavailable('Incomplete history references')
    items = []
    for saved in hits:
        page = pages.get(saved.page_id)
        if page is None or (page.document_id, page.version_id, page.render_sha256, page.embedding_sha256, page.access_version) != (
                saved.document_id, saved.document_version_id, saved.render_sha256, saved.embedding_sha256, saved.access_version):
            continue
        if not math.isfinite(saved.page_score):
            raise SearchUnavailable('Invalid historical score')
        items.append(SearchHit(document_id=page.document_id, document_version_id=page.version_id, page_id=page.id,
            page_index=page.page_index, page_number=page.page_index+1, document_name=page.document_name,
            page_rank=saved.page_rank, page_score=saved.page_score, width_px=page.width_px, height_px=page.height_px,
            render_sha256=page.render_sha256, preview_url=preview_url(row, page.id, page.render_sha256, page.access_version)))
    target = None if history.search_mode == 'library' else any(
        p.document_id == history.target_document_id and p.version_id == history.target_version_id and p.access_version == history.target_access_version for p in pages.values())
    return HistoryDetail(entry=summary(history), q=history.q, k=history.k, search_mode=history.search_mode,
        document_id=history.target_document_id if target else None, target_available=target,
        profile_id=history.profile_id, index_generation=history.index_generation, scope_version=history.scope_version,
        current_scope_version=scope.fingerprint, timings_ms=json.loads(history.timings_json), items=items,
        unavailable_count=history.hit_count-len(items))


def recover_history(engine):
    with account_transaction(engine) as db:
        for marker in db.scalars(select(QueryRequest).where(QueryRequest.status == 'running')):
            marker.status, marker.error_code, marker.updated_at = 'interrupted', 'HISTORY_REQUEST_INTERRUPTED', now()


def fail_request(engine, marker_id, code):
    try:
        with account_transaction(engine) as db:
            marker = db.get(QueryRequest, marker_id)
            if marker is not None and marker.status == 'running':
                marker.status, marker.error_code, marker.updated_at = 'failed', code, now()
    except SQLAlchemyError:
        # The durable running marker remains recoverable if storage is unavailable.
        pass


def search_and_save(request, body):
    engine = request.app.state.engine
    fingerprint = sha(canonical({'q': body.q, 'k': body.k, 'document_id': str(body.document_id) if body.document_id else None}).encode())
    with account_transaction(engine) as db:
        row, user = authorize(request, db, write=True)
        marker = db.scalar(select(QueryRequest).where(QueryRequest.owner_id == user.id, QueryRequest.request_key == str(body.request_id)))
        if marker is not None:
            if marker.input_sha256 != fingerprint:
                raise HTTPException(409, 'HISTORY_REQUEST_INPUT_CHANGED')
            if marker.status == 'completed':
                return HistorySearchResponse(replayed=True, history=detail(request, db, user, row, own(db, user, marker.history_id)))
            code, status = ('HISTORY_DELETED', 410) if marker.status == 'deleted' else (
                'HISTORY_REQUEST_PENDING' if marker.status == 'running' else 'HISTORY_REQUEST_INTERRUPTED' if marker.status == 'interrupted' else 'HISTORY_REQUEST_FAILED', 409)
            raise HTTPException(status, code)
        active = db.scalar(select(func.count()).select_from(QueryHistory).where(QueryHistory.owner_id == user.id))
        running = db.scalar(select(func.count()).select_from(QueryRequest).where(QueryRequest.owner_id == user.id, QueryRequest.status == 'running'))
        if active + running >= MAX_HISTORY:
            raise HTTPException(409, 'HISTORY_LIMIT_REACHED')
        # Reject invalid targets/index identity before creating a reservation.
        allowed_scope(db, user, str(body.document_id) if body.document_id else None)
        marker = QueryRequest(owner_id=user.id, request_key=str(body.request_id), input_sha256=fingerprint)
        db.add(marker); db.flush()
        marker_id, history_id = marker.id, marker.history_id

    def persist(identity, scope, response):
        try:
            with account_transaction(engine) as db:
                row, user = revalidate_search(request, db, identity, scope, response.document_id)
                check_csrf(request, row)
                marker = db.get(QueryRequest, marker_id)
                if marker.status != 'running' or marker.owner_id != user.id:
                    raise HTTPException(409, 'HISTORY_REQUEST_INTERRUPTED')
                target = scope.pages[0] if response.document_id is not None else None
                title = ' '.join(''.join(' ' if unicodedata.category(c).startswith('C') else c for c in body.q).split())[:100] or '查询'
                history = QueryHistory(id=history_id, owner_id=user.id, request_row_id=marker_id, original_title=title,
                    title=title, q=body.q, k=body.k, search_mode=response.search_mode, target_document_id=response.document_id,
                    target_version_id=target.version_id if target else None, target_access_version=target.access_version if target else None,
                    profile_id=scope.profile_id, encoder_sha256=scope.encoder_sha256, index_generation=scope.index_id,
                    scope_version=scope.fingerprint, result_status=response.status, hit_count=len(response.items),
                    timings_json=canonical(response.timings_ms))
                db.add(history); db.flush()
                pages = {p.id: p for p in scope.pages}
                items = []
                for hit in response.items:
                    page = pages[hit.page_id]
                    db.add(QueryHistoryHit(history_id=history_id, page_rank=hit.page_rank, page_id=page.id, document_id=page.document_id,
                        document_version_id=page.version_id, render_sha256=page.render_sha256, embedding_sha256=page.embedding_sha256,
                        access_version=page.access_version, page_score=hit.page_score))
                    items.append(hit.model_copy(update={'preview_url': preview_url(row, page.id, page.render_sha256, page.access_version)}))
                marker.status, marker.updated_at = 'completed', now()
                event(request, db, user, history, 'create'); db.flush()
                result = HistorySearchResponse(replayed=False, history=HistoryDetail(entry=summary(history), q=history.q, k=history.k,
                    search_mode=history.search_mode, document_id=history.target_document_id, target_available=True if target else None,
                    profile_id=history.profile_id, index_generation=history.index_generation, scope_version=history.scope_version,
                    current_scope_version=scope.fingerprint, timings_ms=response.timings_ms, items=items, unavailable_count=0))
            return result
        except SQLAlchemyError:
            raise HTTPException(503, 'HISTORY_SAVE_FAILED') from None
    try:
        return execute_search(request, body, persist)
    except Exception:
        fail_request(engine, marker_id, 'HISTORY_EXECUTION_FAILED')
        raise


def update_history(request, history_id, body):
    with account_transaction(request.app.state.engine) as db:
        _, user = authorize(request, db, write=True)
        history = own(db, user, history_id)
        if history.version != body.version:
            raise HTTPException(409, 'HISTORY_VERSION_CHANGED')
        changed = False
        if 'title' in body.model_fields_set and history.title != body.title:
            history.title, changed = body.title, True
        if 'pinned' in body.model_fields_set and (history.pinned_at is not None) != body.pinned:
            history.pinned_at, changed = now() if body.pinned else None, True
        if changed:
            history.version += 1
            history.updated_at = now()
        event(request, db, user, history, 'update', 'success' if changed else 'noop')
        return summary(history)


def delete_history(request, history_id, body):
    if not body.confirmed:
        raise HTTPException(422, 'CONFIRMATION_REQUIRED')
    with account_transaction(request.app.state.engine) as db:
        _, user = authorize(request, db, write=True)
        history = own(db, user, history_id)
        if history.version != body.version:
            raise HTTPException(409, 'HISTORY_VERSION_CHANGED')
        event(request, db, user, history, 'delete')
        marker = db.get(QueryRequest, history.request_row_id)
        marker.status, marker.updated_at = 'deleted', now()
        db.execute(delete(QueryHistoryHit).where(QueryHistoryHit.history_id == history.id))
        db.delete(history)
