"""Authenticated upload reservations and owner-only metadata polling."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.auth.routes import check_csrf, load_cookie, principal, transaction
from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, Job, JobAttempt, new_id, now
from backend.db.seed import canonical, sha
from .uploads import cleanup_pdf, validate_pdf, write_pdf
from .task_state import retry_available, sync_attempt

router = APIRouter(dependencies=[Depends(load_cookie)])


class JobAttemptResponse(BaseModel):
    attempt: int
    status: str
    stage: str
    progress: int
    error_code: str | None
    cancel_requested_at: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    ended_at: str | None


class JobResponse(BaseModel):
    job_id: str
    document_id: str
    document_version_id: str
    kind: str
    stage: str
    status: str
    progress: int
    attempt: int
    error_code: str | None
    created_at: str
    updated_at: str
    retry_available: bool = False
    cancel_available: bool
    cancel_requested_at: str | None
    display_name: str
    page_count: int
    attempts: list[JobAttemptResponse]


class DocumentResponse(BaseModel):
    document_id: str
    document_version_id: str
    display_name: str
    visibility: str
    status: str
    version: int
    pdf_sha256: str
    page_count: int


def job_response(job, version, db):
    document = db.get(Document, version.document_id)
    history = db.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id).order_by(JobAttempt.attempt)).all()
    return JobResponse(job_id=job.id, document_id=version.document_id, document_version_id=version.id,
                       display_name=document.display_name, page_count=version.page_count,
                       cancel_available=job.status in ("receiving", "queued", "running") and job.cancel_requested_at is None,
                       cancel_requested_at=job.cancel_requested_at, retry_available=retry_available(job, version, document),
                       attempts=[JobAttemptResponse(**{key: getattr(record, key) for key in JobAttemptResponse.model_fields}) for record in history],
                       **{key: getattr(job, key) for key in ("kind", "stage", "status", "progress", "attempt",
                                                           "error_code", "created_at", "updated_at")})


def own_job(db, user, job_id):
    result = db.execute(select(Job, DocumentVersion).join(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id)
                        .where(Job.id == job_id, Job.owner_id == user.id, Document.owner_id == user.id,
                               Document.deleted_at.is_(None), Document.status != "deleted")).one_or_none()
    if result is None:
        raise HTTPException(404, "JOB_NOT_FOUND")
    return result


@router.get("/jobs/{job_id}", response_model=JobResponse, operation_id="get_job", tags=["documents"])
def get_job(job_id: str, request: Request):
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        return job_response(*own_job(db, user, job_id), db)


@router.get("/documents/{document_id}", response_model=DocumentResponse, operation_id="get_document", tags=["documents"])
def get_document(document_id: str, request: Request):
    with Session(request.app.state.engine) as db:
        _, user = principal(request, db, require_changed=True)
        result = db.execute(select(Document, DocumentVersion).join(DocumentVersion, DocumentVersion.document_id == Document.id)
                            .where(Document.id == document_id, Document.owner_id == user.id,
                                   Document.deleted_at.is_(None), Document.status != "deleted")
                            .order_by(DocumentVersion.version.desc()).limit(1)).one_or_none()
        if result is None:
            raise HTTPException(404, "DOCUMENT_NOT_FOUND")
        doc, version = result
        return DocumentResponse(document_id=doc.id, document_version_id=version.id, display_name=doc.display_name,
                                visibility=doc.visibility, status=doc.status, version=version.version,
                                pdf_sha256=version.pdf_sha256, page_count=version.page_count)


def recover_uploads(engine):
    # Single backend worker only. Never turn a reserved upload into searchable data.
    with Session(engine) as db, db.begin():
        for job in db.scalars(select(Job).where(Job.status.in_(("receiving", "running")))):
            job.error_code = "UPLOAD_INTERRUPTED" if job.status == "receiving" else "INGEST_INTERRUPTED"
            job.status = "cancelled" if job.cancel_requested_at else "interrupted"
            if job.status == "cancelled":
                job.error_code = "CANCELLED_BY_OWNER"
            job.updated_at = now()
            sync_attempt(db, job)
        from backend.db.models import IndexGeneration
        db.execute(update(IndexGeneration).where(IndexGeneration.status == "building").values(status="failed"))


def persist_upload(request, identity, key, data, name, count):
    settings = request.app.state.upload_settings
    fingerprint = sha(canonical({"name": name, "sha256": sha(data), "bytes": len(data), "pages": count}).encode())
    with transaction(request) as db:
        row, user = principal(request, db, require_changed=True)
        check_csrf(request, row)
        if identity != (user.id, user.auth_version, row.token_hash):
            raise HTTPException(401, "AUTH_REQUIRED")
        existing = db.scalar(select(Job).where(Job.owner_id == user.id, Job.upload_key == key))
        if existing:
            if existing.request_sha256 != fingerprint:
                raise HTTPException(409, "UPLOAD_KEY_CONFLICT")
            if existing.status == "receiving":
                raise HTTPException(409, "UPLOAD_IN_PROGRESS")
            return job_response(*own_job(db, user, existing.id), db)
        doc_id, version_id, job_id = new_id(), new_id(), new_id()
        base = settings.root.resolve()
        path = (base / doc_id / "source.pdf").resolve()
        if not base.is_relative_to((ROOT / "runtime").resolve()) or not path.is_relative_to(base):
            raise HTTPException(503, "UPLOAD_UNAVAILABLE")
        # This marker explicitly says that no renderer/config has been chosen.
        render_json = canonical({"status": "pending", "stage": "2-1"})
        db.add(Document(id=doc_id, source_key="upload:" + doc_id, owner_id=user.id,
                        display_name=name, visibility="private", status="registered"))
        db.flush()
        version = DocumentVersion(id=version_id, document_id=doc_id, version=1, pdf_sha256=sha(data),
                                  pdf_path=path.relative_to(ROOT).as_posix(), page_count=count,
                                  render_profile_json=render_json, render_profile_sha256=sha(render_json.encode()))
        db.add(version)
        db.flush()
        job = Job(id=job_id, owner_id=user.id, document_version_id=version_id, upload_key=key,
                  request_sha256=fingerprint, upload_bytes=len(data))
        db.add(job)
        db.flush()
        sync_attempt(db, job)
    try:
        write_pdf(path, data)
        with transaction(request) as db:
            row, user = principal(request, db, require_changed=True)
            if identity != (user.id, user.auth_version, row.token_hash):
                raise HTTPException(401, "AUTH_REQUIRED")
            job, version = own_job(db, user, job_id)
            if job.status != "receiving":
                raise HTTPException(409, "UPLOAD_STATE_CHANGED")
            job.status, job.stage, job.updated_at = "queued", "pending", now()
            sync_attempt(db, job)
            db.flush()
            result = job_response(job, version, db)
        return result
    except (OSError, HTTPException, SQLAlchemyError) as exc:
        cleanup_pdf(path)
        error = "UPLOAD_WRITE_FAILED" if isinstance(exc, OSError) else "UPLOAD_NOT_COMMITTED"
        # DB outage may prevent failure recording: receiving becomes interrupted at startup.
        try:
            with Session(request.app.state.engine) as db, db.begin():
                failed = db.get(Job, job_id)
                if failed and failed.status == "receiving":
                    failed.status, failed.error_code, failed.updated_at = "failed", error, now()
                    sync_attempt(db, failed)
        except SQLAlchemyError:
            pass
        if isinstance(exc, HTTPException):
            raise
        return JSONResponse({"detail": error, "job_id": job_id, "document_id": doc_id}, status_code=503)


UPLOAD_SCHEMA = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
    "type": "object", "required": ["file"], "additionalProperties": False,
    "properties": {"file": {"type": "string", "format": "binary"}}}}}},
    "parameters": [{"name": "X-Upload-ID", "in": "header", "required": True, "schema": {"type": "string", "format": "uuid"}},
                   {"name": "X-CSRF-Token", "in": "header", "required": True, "schema": {"type": "string"}}]}


@router.post("/index", response_model=JobResponse, status_code=202, operation_id="upload_pdf", tags=["documents"], openapi_extra=UPLOAD_SCHEMA)
async def upload_pdf(request: Request):
    # Authenticate before multipart parsing; do not bind arbitrary form fields to models.
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db, require_changed=True)
        check_csrf(request, row)
        identity = (user.id, user.auth_version, row.token_hash)
    values = request.headers.getlist("x-upload-id")
    try:
        if len(values) != 1:
            raise ValueError()
        key = str(UUID(values[0]))
    except ValueError:
        raise HTTPException(422, "UPLOAD_ID_REQUIRED") from None
    try:
        async with request.form(max_files=1, max_fields=0) as form:
            items = form.multi_items()
            if len(items) != 1 or items[0][0] != "file" or not isinstance(items[0][1], UploadFile):
                raise HTTPException(422, "SINGLE_PDF_REQUIRED")
            file = items[0][1]
            data = await file.read(request.app.state.upload_settings.max_bytes + 1)
            count = await run_in_threadpool(validate_pdf, data, file.filename, file.content_type, request.app.state.upload_settings)
            return await run_in_threadpool(persist_upload, request, identity, key, data, file.filename, count)
    except StarletteHTTPException as exc:
        if exc.status_code == 400:
            raise HTTPException(422, "INVALID_MULTIPART") from None
        raise
    except OSError:
        raise HTTPException(503, "UPLOAD_UNAVAILABLE") from None
