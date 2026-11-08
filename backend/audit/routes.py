from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from backend.auth.routes import load_cookie
from .schemas import EventQuery, TaskQuery, AuditEventList, AuditTaskList
from .service import listing

router = APIRouter(prefix='/admin', tags=['audit'], dependencies=[Depends(load_cookie)])

def unique(request):
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, 'INVALID_REQUEST')

@router.get('/events', response_model=AuditEventList, operation_id='list_audit_events')
def events(request: Request, params: Annotated[EventQuery, Query()]):
    unique(request)
    return listing(request, params, True)

@router.get('/tasks', response_model=AuditTaskList, operation_id='list_audit_tasks')
def tasks(request: Request, params: Annotated[TaskQuery, Query()]):
    unique(request)
    return listing(request, params, False)
