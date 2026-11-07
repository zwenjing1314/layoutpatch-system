"""Owner-only persistent task discovery and attempt-bound writes."""
import base64
import hashlib
import hmac
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.auth.routes import check_csrf, load_cookie, principal, transaction
from backend.db.models import Document, DocumentVersion, Job, now
from backend.db.seed import canonical, sha
from .ingest import JobResponse, job_response, own_job
from .task_state import MAX_ATTEMPTS, retry_available, retry_source, sync_attempt

router = APIRouter(dependencies=[Depends(load_cookie)])


class JobListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=10, ge=1, le=50)
    cursor: str | None = Field(default=None, min_length=1, max_length=2048)


class JobListResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None


class JobActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt: int = Field(ge=1, le=MAX_ATTEMPTS)


def cursor_encode(data, token):
    raw = canonical(data).encode()
    signature = hmac.new(token.encode(), b"job-list-v1\0" + raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + signature).decode().rstrip("=")


def cursor_decode(value, token, limit):
    try:
        packed = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        raw, signature = packed[:-32], packed[-32:]
        if not hmac.compare_digest(signature, hmac.new(token.encode(), b"job-list-v1\0" + raw, hashlib.sha256).digest()):
            raise ValueError()
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {"v", "limit", "after", "created"}
                or data["v"] != 1 or data["limit"] != limit
                or not isinstance(data["after"], str) or not isinstance(data["created"], str)):
            raise ValueError()
        return data
    except (ValueError, TypeError, UnicodeError):
        raise HTTPException(422, "INVALID_JOB_CURSOR") from None


@router.get("/jobs", response_model=JobListResponse, operation_id="list_jobs", tags=["documents"])
def list_jobs(request: Request, params: Annotated[JobListInput, Query()]):
    if any(len(request.query_params.getlist(key)) != 1 for key in request.query_params):
        raise HTTPException(422, "INVALID_REQUEST")
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db, require_changed=True)
        query = (select(Job, DocumentVersion).join(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id)
                 .where(Job.owner_id == user.id, Document.owner_id == user.id, Document.deleted_at.is_(None), Document.status != "deleted"))
        if params.cursor:
            after = cursor_decode(params.cursor, row.csrf_token, params.limit)
            query = query.where(or_(Job.created_at < after["created"], and_(Job.created_at == after["created"], Job.id < after["after"])))
        rows = db.execute(query.order_by(Job.created_at.desc(), Job.id.desc()).limit(params.limit + 1)).all()
        cursor = None
        if len(rows) > params.limit:
            last = rows[params.limit - 1][0]
            cursor = cursor_encode({"v": 1, "limit": params.limit, "after": last.id, "created": last.created_at}, row.csrf_token)
        return JobListResponse(items=[job_response(job, version, db) for job, version in rows[:params.limit]], next_cursor=cursor)


def checked_job(request, db, job_id, attempt):
    row, user = principal(request, db, require_changed=True)
    check_csrf(request, row)
    job, version = own_job(db, user, job_id)
    if job.attempt != attempt:
        raise HTTPException(409, "JOB_ATTEMPT_CHANGED")
    return job, version, db.get(Document, version.document_id)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse, operation_id="retry_job", tags=["documents"])
def retry_job(job_id: str, action: JobActionInput, request: Request):
    with transaction(request) as db:
        job, version, doc = checked_job(request, db, job_id, action.attempt)
        if not retry_available(job, version, doc):
            raise HTTPException(409, "JOB_NOT_RETRYABLE")
        source = retry_source(version)
        try:
            with source.open("rb") as stream:
                data = stream.read(min(job.upload_bytes, 20 * 1024 * 1024) + 1)
            if len(data) != job.upload_bytes or sha(data) != version.pdf_sha256:
                raise ValueError()
        except (OSError, ValueError):
            raise HTTPException(409, "REUPLOAD_REQUIRED") from None
        sync_attempt(db, job)
        db.flush()
        job.attempt += 1
        job.status, job.stage, job.progress, job.error_code = "queued", "pending", 0, None
        job.cancel_requested_at, job.updated_at = None, now()
        sync_attempt(db, job)
        db.flush()
        return job_response(job, version, db)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse, operation_id="cancel_job", tags=["documents"])
def cancel_job(job_id: str, action: JobActionInput, request: Request):
    with transaction(request) as db:
        job, version, _ = checked_job(request, db, job_id, action.attempt)
        if job.status == "cancelled":
            return job_response(job, version, db)
        if job.status not in ("receiving", "queued", "running"):
            raise HTTPException(409, "JOB_NOT_CANCELLABLE")
        job.cancel_requested_at = job.cancel_requested_at or now()
        job.updated_at = now()
        if job.status != "running":
            job.status, job.error_code = "cancelled", "CANCELLED_BY_OWNER"
        sync_attempt(db, job)
        db.flush()
        return job_response(job, version, db)
