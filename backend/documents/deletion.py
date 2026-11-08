"""Owner-only tombstone transaction and durable cleanup discovery/control."""
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.accounts import account_transaction
from backend.auth.routes import check_csrf, load_cookie, principal
from backend.db.models import Document, DocumentCleanup, DocumentVersion, DeletionEvent, Job, ParsingTask, now
from backend.db.seed import canonical, sha
from .task_state import sync_attempt

router = APIRouter(prefix='/documents', tags=['deletion'], dependencies=[Depends(load_cookie)])


class DeletionDocument(BaseModel):
    document_id: str
    display_name: str
    document_version_id: str | None
    access_version: int
    status: str
    cleanup_id: str | None
    cleanup_status: str | None
    attempt: int | None
    stage: str | None
    error_code: str | None


class DeletionList(BaseModel):
    items: list[DeletionDocument]
    next_offset: int | None
    scope_version: str


class DeletionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_version_id: UUID | None
    access_version: int = Field(strict=True, ge=1)
    confirmed: StrictBool


class CleanupRetryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attempt: int = Field(strict=True, ge=1)
    confirmed: StrictBool


def view(db, doc):
    task = db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id == doc.id))
    return DeletionDocument(document_id=doc.id, display_name=doc.display_name,
        document_version_id=doc.active_version_id, access_version=doc.access_version, status=doc.status,
        cleanup_id=task.id if task else None, cleanup_status=task.status if task else None,
        attempt=task.attempt if task else None, stage=task.stage if task else None, error_code=task.error_code if task else None)


def own(db, user, document_id):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.owner_id == user.id))
    if doc is None:
        raise HTTPException(404, 'DOCUMENT_NOT_FOUND')
    return doc


def event(db, actor_id, doc, action, outcome, code, attempt, timestamp):
    db.add(DeletionEvent(actor_id=actor_id, document_id=doc.id, action=action, outcome=outcome,
                         code=code, attempt=attempt, occurred_at=timestamp))


def delete_document(engine, document_id, body, authorize, settings, timestamp=None):
    if not body.confirmed:
        raise HTTPException(422, 'CONFIRMATION_REQUIRED')
    timestamp = time.time() if timestamp is None else timestamp
    failure = None
    with account_transaction(engine) as db:
        user = authorize(db)  # Recheck cookie/version/first change/CSRF AFTER write lock.
        doc = own(db, user, document_id)
        task = db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id == doc.id))
        expected = str(body.document_version_id) if body.document_version_id else None
        if doc.status == 'deleted' and task:
            # An exact replay of the pre-tombstone identity is idempotent.
            manifest = json.loads(task.manifest_json)
            if (body.access_version, expected) not in ((doc.access_version, doc.active_version_id),
                    (manifest.get('access_version'), manifest.get('active_version_id'))):
                failure = 'DELETION_INPUT_CHANGED'
        elif body.access_version != doc.access_version or expected != doc.active_version_id:
            failure = 'DELETION_INPUT_CHANGED'
        if failure:
            event(db, user.id, doc, 'delete', 'rejected', failure, task.attempt if task else 1, timestamp)
        elif task is None:
            from .cleanup import build_manifest
            manifest = build_manifest(db, doc, settings)
            doc.status, doc.deleted_at, doc.visibility = 'deleted', now(), 'private'
            doc.access_version += 1
            task = DocumentCleanup(document_id=doc.id, manifest_json=canonical(manifest))
            db.add(task)
            versions = select(DocumentVersion.id).where(DocumentVersion.document_id == doc.id)
            for job in db.scalars(select(Job).where(Job.document_version_id.in_(versions), Job.status.in_(['receiving', 'queued', 'running']))):
                job.cancel_requested_at, job.updated_at = now(), now()
                if job.status == 'queued':
                    job.status, job.error_code = 'cancelled', 'DOCUMENT_DELETED'
                sync_attempt(db, job)
            for parsing in db.scalars(select(ParsingTask).where(ParsingTask.document_version_id.in_(versions), ParsingTask.status == 'queued')):
                parsing.status, parsing.error_code, parsing.updated_at = 'interrupted', 'DOCUMENT_DELETED', now()
            db.flush()
            event(db, user.id, doc, 'delete', 'success', 'OK', task.attempt, timestamp)
        else:
            event(db, user.id, doc, 'delete', 'noop', 'OK', task.attempt, timestamp)
        db.flush()
        result = view(db, doc)
    if failure:
        raise HTTPException(409, failure)
    return result


def authorize(request, db):
    row, user = principal(request, db, require_changed=True)
    check_csrf(request, row)
    return user


@router.get('/deletion', response_model=DeletionList, operation_id='list_deletion_documents')
def listing(request: Request, limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)):
    if any(k not in ('limit', 'offset') or len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, 'INVALID_REQUEST')
    def snapshot(db, user):
        items = [view(db, doc) for doc in db.scalars(select(Document).where(Document.owner_id == user.id).order_by(Document.created_at.desc(), Document.id))]
        return items, sha(canonical({'identity': (user.id, user.auth_version), 'items': [i.model_dump() for i in items]}).encode())
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        items, stamp = snapshot(db, user)
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        if snapshot(db, user)[1] != stamp:
            raise HTTPException(409, 'DELETION_LIST_CHANGED')
    return DeletionList(items=items[offset:offset+limit], next_offset=offset+limit if offset+limit < len(items) else None, scope_version=stamp)


@router.post('/{document_id}/delete', response_model=DeletionDocument, status_code=202, operation_id='delete_own_document')
def delete_own(document_id: UUID, body: DeletionInput, request: Request):
    if request.query_params:
        raise HTTPException(422, 'INVALID_REQUEST')
    return delete_document(request.app.state.engine, str(document_id), body, lambda db: authorize(request, db),
                           request.app.state.cleanup.settings, request.app.state.clock())


@router.get('/{document_id}/cleanup', response_model=DeletionDocument, operation_id='get_document_cleanup')
def status(document_id: UUID, request: Request):
    if request.query_params:
        raise HTTPException(422, 'INVALID_REQUEST')
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        return view(db, own(db, user, str(document_id)))


@router.post('/{document_id}/cleanup/retry', response_model=DeletionDocument, status_code=202, operation_id='retry_document_cleanup')
def retry(document_id: UUID, body: CleanupRetryInput, request: Request):
    if request.query_params or not body.confirmed:
        raise HTTPException(422, 'CONFIRMATION_REQUIRED')
    failure = None
    with account_transaction(request.app.state.engine) as db:
        user = authorize(request, db)
        doc = own(db, user, str(document_id))
        task = db.scalar(select(DocumentCleanup).where(DocumentCleanup.document_id == doc.id))
        if task is None or doc.status != 'deleted':
            raise HTTPException(409, 'CLEANUP_NOT_REQUESTED')
        if task.attempt != body.attempt:
            failure = 'CLEANUP_ATTEMPT_CHANGED'
        elif task.status == 'failed':
            task.attempt += 1
            task.status, task.stage, task.error_code, task.updated_at = 'queued', 'waiting', None, now()
            outcome = 'success'
        else:
            outcome = 'noop'
        event(db, user.id, doc, 'retry', 'rejected' if failure else outcome, failure or 'OK', task.attempt, request.app.state.clock())
        db.flush()
        result = view(db, doc)
    if failure:
        raise HTTPException(409, failure)
    return result
