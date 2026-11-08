"""Authorized status only; candidate/text/image endpoints belong to later batches."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.routes import check_csrf, load_cookie, principal, transaction
from backend.db.models import Document, Page, PageParse, ParserProfile, ParsingTask, User
from backend.documents.access import visible_document
from .candidates import ParseError
from .runner import enqueue

router = APIRouter(dependencies=[Depends(load_cookie)])


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_task_id: UUID | None = None


class PageParseStatus(BaseModel):
    page_id: str
    page_index: int
    page_number: int
    render_sha256: str
    width_px: int
    height_px: int
    status: Literal["pending","running","ready","no_candidates","failed","timeout","interrupted"]
    candidate_count: int
    candidate_hash: str | None
    error_code: str | None


class ParsingResponse(BaseModel):
    document_id: str
    document_version_id: str | None
    task_id: str | None
    parser_profile_id: str | None
    parser_profile_sha256: str | None
    attempt: int | None
    status: Literal["not_requested","queued","running","ready","partial","failed","interrupted"]
    error_code: str | None
    pages: list[PageParseStatus]


def authorized_document(db,user,document_id):
    doc = db.scalar(select(Document).join(User,User.id == Document.owner_id).where(Document.id == document_id,visible_document(user)))
    if doc is None:
        raise HTTPException(404,"DOCUMENT_NOT_FOUND")
    return doc


def status_response(db,doc,task=None):
    task = task or db.scalar(select(ParsingTask).where(ParsingTask.document_version_id == doc.active_version_id)
                            .order_by(ParsingTask.created_at.desc(),ParsingTask.id.desc()).limit(1))
    if not task:
        return ParsingResponse(document_id=doc.id,document_version_id=doc.active_version_id,task_id=None,parser_profile_id=None,
            parser_profile_sha256=None,attempt=None,status="not_requested",error_code=None,pages=[])
    profile = db.get(ParserProfile,task.parser_profile_id)
    rows = db.execute(select(PageParse,Page).join(Page,Page.id == PageParse.page_id).where(PageParse.task_id == task.id,
        Page.document_version_id == doc.active_version_id).order_by(Page.page_index)).all()
    return ParsingResponse(document_id=doc.id,document_version_id=task.document_version_id,task_id=task.id,parser_profile_id=profile.id,
        parser_profile_sha256=profile.config_sha256,attempt=task.attempt,status=task.status,error_code=task.error_code,
        pages=[PageParseStatus(page_id=p.id,page_index=p.page_index,page_number=p.page_index+1,**{name:getattr(record,name)
            for name in ("render_sha256","width_px","height_px","status","candidate_count","candidate_hash","error_code")}) for record,p in rows])


@router.get("/documents/{document_id}/parsing",response_model=ParsingResponse,operation_id="get_document_parsing",tags=["documents"])
def get_parsing(document_id: str,request: Request):
    with Session(request.app.state.engine) as db:
        _,user = principal(request,db,require_changed=True)
        doc = authorized_document(db,user,document_id)
        return status_response(db,doc)


@router.post("/documents/{document_id}/parsing",response_model=ParsingResponse,status_code=202,operation_id="request_document_parsing",tags=["documents"])
def request_parsing(document_id: str,action: ParseRequest,request: Request):
    with transaction(request) as db:
        row,user = principal(request,db,require_changed=True)
        check_csrf(request,row)
        doc = authorized_document(db,user,document_id)
        if doc.owner_id != user.id:
            raise HTTPException(404,"DOCUMENT_NOT_FOUND")
        try:
            task = enqueue(db,doc,retry_task_id=str(action.retry_task_id) if action.retry_task_id else None)
            return status_response(db,doc,task)
        except ParseError as exc:
            raise HTTPException(503 if exc.code == "PARSER_RESOURCES_UNAVAILABLE" else 409,exc.code) from None
