from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.auth.routes import load_cookie
from backend.search.qdrant import SearchUnavailable
from .schemas import (HistoryDeleteInput, HistoryDeleteResponse, HistoryDetail, HistoryList,
                      HistorySearchInput, HistorySearchResponse, HistorySummary, HistoryUpdateInput)
from .service import MAX_HISTORY, authorize, delete_history, detail, list_snapshot, own, search_and_save, update_history

router = APIRouter(tags=['history'], dependencies=[Depends(load_cookie)])


def no_query(request):
    if request.query_params:
        raise HTTPException(422, 'INVALID_REQUEST')


@router.post('/search', response_model=HistorySearchResponse, operation_id='search_and_record_history')
def recorded_search(body: HistorySearchInput, request: Request):
    no_query(request)
    try:
        return search_and_save(request, body)
    except SearchUnavailable:
        raise HTTPException(503, 'SEARCH_UNAVAILABLE') from None


@router.get('/history', response_model=HistoryList, operation_id='list_query_history')
def listing(request: Request, limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)):
    if any(k not in ('limit', 'offset') or len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, 'INVALID_REQUEST')
    with Session(request.app.state.engine) as db:
        _, user = authorize(request, db)
        items, stamp = list_snapshot(db, user)
    with Session(request.app.state.engine) as db:
        _, user = authorize(request, db)
        if list_snapshot(db, user)[1] != stamp:
            raise HTTPException(409, 'HISTORY_LIST_CHANGED')
    return HistoryList(items=items[offset:offset+limit], next_offset=offset+limit if offset+limit < len(items) else None,
                       scope_version=stamp, limit_per_user=MAX_HISTORY)


@router.get('/history/{history_id}', response_model=HistoryDetail, operation_id='get_query_history')
def get_detail(history_id: UUID, request: Request):
    no_query(request)
    def read(db):
        row, user = authorize(request, db)
        return detail(request, db, user, row, own(db, user, str(history_id)))
    try:
        with Session(request.app.state.engine) as db:
            first = read(db)
        with Session(request.app.state.engine) as db:
            second = read(db)
        if first != second:
            raise HTTPException(409, 'HISTORY_INPUT_CHANGED')
        return second
    except SearchUnavailable:
        raise HTTPException(503, 'HISTORY_REFERENCES_UNAVAILABLE') from None


@router.patch('/history/{history_id}', response_model=HistorySummary, operation_id='update_query_history')
def update(history_id: UUID, body: HistoryUpdateInput, request: Request):
    no_query(request)
    return update_history(request, str(history_id), body)


@router.delete('/history/{history_id}', response_model=HistoryDeleteResponse, operation_id='delete_query_history')
def remove(history_id: UUID, body: HistoryDeleteInput, request: Request):
    no_query(request)
    delete_history(request, str(history_id), body)
    return HistoryDeleteResponse(history_id=str(history_id))
