"""Owner-admin sharing only. Visibility, authorization generation and event commit together."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.auth.accounts import account_transaction
from backend.auth.routes import check_csrf, load_cookie, principal
from backend.db.models import Document, SharingEvent
from backend.db.seed import canonical, sha
from .listing import list_snapshot
from .names import normalize_name

router=APIRouter(prefix='/admin/documents',tags=['sharing'],dependencies=[Depends(load_cookie)])

class SharingDocument(BaseModel):
    document_id: str
    display_name: str
    document_version_id: str | None
    version: int | None
    page_count: int | None
    visibility: Literal['private','shared']
    status: str
    access_version: int
    can_publish: bool

class SharingList(BaseModel):
    items: list[SharingDocument]
    next_offset: int | None
    scope_version: str

class SharingInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    document_version_id: UUID | None
    access_version: int=Field(strict=True,ge=1)
    confirmed: StrictBool

class SharingMutation(BaseModel):
    document: SharingDocument
    changed: bool

def snapshot(db,user,name=''):
    # list_snapshot applies the ordinary own+shared contract. Filter to own
    # before returning ANY management metadata; other admins' shares are not managed here.
    items,_=list_snapshot(db,user,name)
    docs={d.id:d for d in db.scalars(select(Document).where(Document.owner_id==user.id,Document.deleted_at.is_(None),Document.status!='deleted'))}
    result=[SharingDocument(document_id=i.document_id,display_name=i.display_name,document_version_id=docs[i.document_id].active_version_id,
        version=i.version,page_count=i.page_count,visibility=i.visibility,status=i.status,access_version=docs[i.document_id].access_version,
        can_publish=i.searchable) for i in items if i.access=='own' and i.document_id in docs]
    fingerprint=sha(canonical({'identity':(user.id,user.role,user.auth_version),'items':[i.model_dump() for i in result]}).encode())
    return result,fingerprint

@router.get('',response_model=SharingList,operation_id='list_sharing_documents')
def listing(request:Request,name:str=Query('',max_length=255),limit:int=Query(10,ge=1,le=100),offset:int=Query(0,ge=0,le=1000000)):
    if any(k not in ('name','limit','offset') or len(request.query_params.getlist(k))!=1 for k in request.query_params):
        raise HTTPException(422,'INVALID_REQUEST')
    name=normalize_name(name.strip())
    with Session(request.app.state.engine) as db:
        _,user=principal(request,db,require_changed=True,admin=True)
        items,stamp=snapshot(db,user,name)
        selected=items[offset:offset+limit]
    with Session(request.app.state.engine) as db:
        _,user=principal(request,db,require_changed=True,admin=True)
        if snapshot(db,user,name)[1]!=stamp:raise HTTPException(409,'SHARING_LIST_CHANGED')
    return SharingList(items=selected,next_offset=offset+limit if offset+limit<len(items) else None,scope_version=stamp)

def change_sharing(engine,document_id,action,body,timestamp,authorize):
    if action not in ('publish','unpublish') or not body.confirmed:raise HTTPException(422,'CONFIRMATION_REQUIRED')
    failure=None;result=None
    with account_transaction(engine) as db:
        user=authorize(db) # Current principal/CSRF checked AFTER acquiring the SQLite write lock.
        doc=db.scalar(select(Document).where(Document.id==document_id,Document.owner_id==user.id,
                      Document.deleted_at.is_(None),Document.status!='deleted'))
        if not doc:raise HTTPException(404,'DOCUMENT_NOT_FOUND')
        before=doc.access_version;desired='shared' if action=='publish' else 'private'
        if (str(body.document_version_id) if body.document_version_id else None)!=doc.active_version_id or body.access_version!=before:
            failure='SHARING_INPUT_CHANGED'
        elif action=='publish' and not next(i for i in snapshot(db,user)[0] if i.document_id==doc.id).can_publish:
            failure='DOCUMENT_NOT_READY'
        if failure:
            outcome='rejected';changed=False
        else:
            changed=doc.visibility!=desired
            if changed:doc.visibility=desired;doc.access_version+=1
            outcome='success' if changed else 'noop'
            db.flush()
            item=next(i for i in snapshot(db,user)[0] if i.document_id==doc.id)
            result=SharingMutation(document=item,changed=changed)
        db.add(SharingEvent(actor_id=user.id,document_id=doc.id,action=action,outcome=outcome,code=failure or 'OK',
            before_version=before,after_version=doc.access_version,occurred_at=timestamp))
    if failure:raise HTTPException(409,failure)
    return result

def invoke(request,document_id,action,body):
    if request.query_params:raise HTTPException(422,'INVALID_REQUEST')
    def authorize(db):
        row,user=principal(request,db,require_changed=True,admin=True);check_csrf(request,row);return user
    return change_sharing(request.app.state.engine,str(document_id),action,body,request.app.state.clock(),authorize)

@router.post('/{document_id}/publish',response_model=SharingMutation,operation_id='publish_document')
def publish(document_id:UUID,body:SharingInput,request:Request):return invoke(request,document_id,'publish',body)

@router.post('/{document_id}/unpublish',response_model=SharingMutation,operation_id='unpublish_document')
def unpublish(document_id:UUID,body:SharingInput,request:Request):return invoke(request,document_id,'unpublish',body)
