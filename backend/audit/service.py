"""Explicit projections: never select private content, hashes, paths or manifests."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import cast, func, Integer, literal, select, union_all
from sqlalchemy.orm import Session
from backend.auth.routes import principal
from backend.db.models import (AccountEvent, SharingEvent, DeletionEvent, HistoryEvent,
    Job, Document, DocumentVersion, ParsingTask, DocumentCleanup, QueryRequest)
from backend.db.seed import canonical, sha
from .schemas import AuditEventItem, AuditTaskItem

DAY = 86400
# Whitelist, not a regex: corrupted/imported fields must never leak free text.
EVENT_CODES = frozenset(('OK', 'LAST_ACTIVE_ADMIN', 'ACCOUNT_NOT_FOUND', 'USERNAME_EXISTS',
    'SHARING_INPUT_CHANGED', 'DOCUMENT_NOT_READY', 'DELETION_INPUT_CHANGED', 'CLEANUP_ATTEMPT_CHANGED',
    'CLEANUP_NOT_RETRYABLE', 'CLEANUP_FAILED', 'CLEANUP_STORAGE_FAILED', 'CLEANUP_INDEX_UNAVAILABLE',
    'CLEANUP_INTERRUPTED', 'CLEANUP_PATH_REJECTED', 'CLEANUP_REFERENCE_CONFLICT', 'CLEANUP_CACHE_REJECTED'))
TASK_CODES = EVENT_CODES | frozenset(('MODEL_BUSY', 'PAGE_ENCODING_FAILED', 'INDEX_UNAVAILABLE',
    'RENDER_FAILED', 'RENDER_TIMEOUT', 'INGEST_STORAGE_FAILED', 'METADATA_UNAVAILABLE', 'INGEST_FAILED',
    'INGEST_INTERRUPTED', 'CANCELLED_BY_OWNER', 'UPLOAD_INTERRUPTED', 'UPLOAD_FAILED',
    'PARSER_INTERRUPTED', 'PARSER_AUTHORITY_CHANGED', 'PARSER_INPUT_CHANGED', 'PARSER_EXECUTION_FAILED',
    'PARSER_PAGE_ERRORS', 'PARSER_TIMEOUT', 'PARSER_DEADLINE_EXCEEDED', 'HISTORY_REQUEST_INTERRUPTED',
    'HISTORY_EXECUTION_FAILED', 'HISTORY_SAVE_FAILED'))
STAGES = frozenset(('upload', 'pending', 'rendering', 'encoding', 'indexing', 'activating', 'completed',
    'waiting', 'index', 'files', 'metadata', 'done', 'parsing', 'request'))

def safe_time(value):
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, AttributeError):
        return None

def window(request, params):
    for key in ('since', 'until', 'limit', 'offset'):
        if key in request.query_params and (not request.query_params[key].isascii() or not request.query_params[key].isdecimal()):
            raise HTTPException(422, 'INVALID_REQUEST')
    end = params.until if params.until is not None else int(request.app.state.clock()) + 1
    start = params.since if params.since is not None else max(0, end - 7*DAY)
    if not 0 < end-start <= 31*DAY: raise HTTPException(422, 'AUDIT_WINDOW_INVALID')
    return start, end

def event_query(params, start, end):
    parts = []
    for model, kind, target, code, actor_type in (
        (AccountEvent, 'account', AccountEvent.target_id, AccountEvent.code, AccountEvent.source),
        (SharingEvent, 'sharing', SharingEvent.document_id, SharingEvent.code, literal('user')),
        (DeletionEvent, 'deletion', DeletionEvent.document_id, DeletionEvent.code, literal('user')),
        (HistoryEvent, 'history', HistoryEvent.history_id, literal('OK'), literal('user'))):
        parts.append(select(model.id.label('event_id'), literal(kind).label('category'), model.actor_id,
            target.label('target_id'), actor_type.label('actor_type'), model.action, model.outcome,
            code.label('code'), model.occurred_at).where(model.occurred_at >= start, model.occurred_at < end))
    rows = union_all(*parts).subquery(); query = select(rows)
    for key in ('category', 'actor_id', 'target_id', 'outcome'):
        value = getattr(params, key)
        if value is not None: query = query.where(rows.c[key] == str(value))
    return query.order_by(rows.c.occurred_at.desc(), rows.c.category, rows.c.event_id)

def task_query(params, start, end):
    rows = union_all(
        select(Job.id.label('task_id'), literal('ingest').label('kind'), Job.owner_id,
            Document.id.label('document_id'), Job.status, Job.stage, Job.attempt, Job.progress, Job.error_code,
            Job.created_at, Job.updated_at).join(DocumentVersion, Job.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id),
        select(ParsingTask.id, literal('parsing'), Document.owner_id, Document.id, ParsingTask.status,
            literal('parsing'), ParsingTask.attempt, literal(None), ParsingTask.error_code, ParsingTask.created_at,
            ParsingTask.updated_at).join(DocumentVersion, ParsingTask.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id),
        select(DocumentCleanup.id, literal('cleanup'), Document.owner_id, Document.id, DocumentCleanup.status,
            DocumentCleanup.stage, DocumentCleanup.attempt, literal(None), DocumentCleanup.error_code,
            DocumentCleanup.created_at, DocumentCleanup.updated_at).join(Document, DocumentCleanup.document_id == Document.id),
        select(QueryRequest.id, literal('search'), QueryRequest.owner_id, literal(None), QueryRequest.status,
            literal('request'), literal(1), literal(None), QueryRequest.error_code, QueryRequest.created_at,
            QueryRequest.updated_at)).subquery()
    timestamp = cast(func.strftime('%s', rows.c.updated_at), Integer)
    query = select(rows).where(timestamp >= start, timestamp < end)
    for key in ('kind', 'status', 'owner_id', 'document_id'):
        value = getattr(params, key)
        if value is not None: query = query.where(rows.c[key] == str(value))
    return query.order_by(timestamp.desc(), rows.c.updated_at.desc(), rows.c.kind, rows.c.task_id)

def snapshot(db, user, params, start, end, events):
    rows = db.execute((event_query if events else task_query)(params, start, end)).mappings(); items = []
    for row in rows:
        value = dict(row)
        if events:
            value['actor_type'] = 'cli' if value['actor_type'] == 'cli' else 'system' if value['actor_id'] is None else 'user'
            value['code'] = value['code'] if value['code'] in EVENT_CODES else 'OTHER'
            item = AuditEventItem(**value)
        else:
            value['error_code'] = value['error_code'] if value['error_code'] is None or value['error_code'] in TASK_CODES else 'OTHER'
            value['stage'] = value['stage'] if value['stage'] in STAGES else 'other'
            value['created_at'] = safe_time(value['created_at'])
            value['updated_at'] = safe_time(value['updated_at'])
            item = AuditTaskItem(**value)
        items.append(item)
    filters = params.model_dump(mode='json', exclude={'offset', 'since', 'until'})
    stamp = sha(canonical({'identity': (user.id, user.role, user.auth_version), 'filters': filters,
        'since': start, 'until': end, 'items': [i.model_dump() for i in items]}).encode())
    return items, stamp

def listing(request, params, events):
    start, end = window(request, params)
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True, admin=True)
        _, stamp = snapshot(db, user, params, start, end, events)
    # A fresh transaction also catches a cookie loaded before revocation/role change.
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True, admin=True)
        items, current = snapshot(db, user, params, start, end, events)
    if stamp != current: raise HTTPException(409, 'AUDIT_LIST_CHANGED')
    offset, limit = params.offset, params.limit
    return dict(items=items[offset:offset+limit], next_offset=offset+limit if offset+limit < len(items) else None,
        scope_version=current, since=start, until=end)
