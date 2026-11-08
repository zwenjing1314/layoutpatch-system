"""Account management API. No private-document bypass."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import User
from .accounts import AccountError, account_view, change_account, create_account
from .routes import check_csrf, load_cookie, principal

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(load_cookie)])


class AccountResponse(BaseModel):
    user_id: str
    username: str
    role: Literal["admin", "user"]
    active: bool
    must_change_password: bool
    created_at: str
    updated_at: str


class AccountList(BaseModel):
    items: list[AccountResponse]
    next_offset: int | None


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: SecretStr = Field(min_length=12, max_length=128)
    role: Literal["admin", "user"] = "user"


class AccountActive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: StrictBool


class AccountReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr = Field(min_length=12, max_length=128)


class AccountRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountMutation(BaseModel):
    account: AccountResponse
    changed: bool


def authorize(request):
    def check(db):
        row, user = principal(request, db, require_changed=True, admin=True)
        check_csrf(request, row)
        return user.id
    return check


def invoke(request, callback):
    if request.query_params:
        raise HTTPException(422, "INVALID_REQUEST")
    try:
        return callback()
    except AccountError as exc:
        raise HTTPException(exc.status, exc.code) from None


@router.get("", response_model=AccountList, operation_id="list_accounts")
def list_accounts(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)):
    with Session(request.app.state.engine) as db:
        principal(request, db, require_changed=True, admin=True)
        if any(key not in ("limit", "offset") or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
            raise HTTPException(422, "INVALID_REQUEST")
        rows = list(db.scalars(select(User).order_by(User.username, User.id).offset(offset).limit(limit+1)))
        return AccountList(items=[AccountResponse(**account_view(u)) for u in rows[:limit]],
                           next_offset=offset+limit if len(rows)>limit else None)


@router.post("", response_model=AccountMutation, status_code=201, operation_id="create_account")
def create(body: AccountCreate, request: Request):
    return invoke(request, lambda: create_account(request.app.state.engine, body.username, body.password.get_secret_value(),
                  body.role, request.app.state.clock(), authorize=authorize(request)))


@router.patch("/{user_id}", response_model=AccountMutation, operation_id="set_account_active")
def active(user_id: UUID, body: AccountActive, request: Request):
    return invoke(request, lambda: change_account(request.app.state.engine, None, "enable" if body.active else "disable",
                  request.app.state.clock(), user_id=str(user_id), authorize=authorize(request)))


@router.post("/{user_id}/password", response_model=AccountMutation, operation_id="reset_account_password")
def reset(user_id: UUID, body: AccountReset, request: Request):
    return invoke(request, lambda: change_account(request.app.state.engine, None, "reset", request.app.state.clock(),
                  body.password.get_secret_value(), user_id=str(user_id), authorize=authorize(request)))


@router.post("/{user_id}/sessions/revoke", response_model=AccountMutation, operation_id="revoke_account_sessions")
def revoke(user_id: UUID, body: AccountRevoke, request: Request):
    return invoke(request, lambda: change_account(request.app.state.engine, None, "revoke", request.app.state.clock(),
                  user_id=str(user_id), authorize=authorize(request)))
