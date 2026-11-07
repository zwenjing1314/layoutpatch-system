from contextlib import contextmanager
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starsessions import get_session_handler, load_session, regenerate_session_id

from backend.db.models import AuthSession, LoginAttempt, PipelineProfile, User, now
from backend.db.seed import password_hasher
from .store import digest

router = APIRouter()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class MeResponse(BaseModel):
    user_id: str
    username: str
    role: str
    must_change_password: bool
    csrf_token: str


class ProfileResponse(BaseModel):
    name: str
    config_sha256: str
    status: str


async def load_cookie(request: Request):
    try:
        await load_session(request)
    except SQLAlchemyError:
        # starsessions 2.2.1 marks loaded before store.read finishes. On a failed
        # read, prevent send_wrapper from inspecting its still-unloaded guard.
        get_session_handler(request).is_loaded = False
        request.scope["session"] = {}
        raise HTTPException(503, "SERVICE_UNAVAILABLE") from None


@contextmanager
def transaction(request):
    with request.app.state.engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                yield db
                db.flush()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def principal(request, db, require_changed=False, admin=False):
    token = request.cookies.get(request.app.state.settings.cookie_name, "")
    row = db.get(AuthSession, digest(token)) if token else None
    user = db.get(User, row.user_id) if row else None
    if not request.app.state.store.valid(row, user, request.app.state.clock()) or request.session.get("user_id") != user.id:
        raise HTTPException(401, "AUTH_REQUIRED")
    if require_changed and user.must_change_password:
        raise HTTPException(403, "PASSWORD_CHANGE_REQUIRED")
    if admin and user.role != "admin":
        raise HTTPException(403, "ADMIN_REQUIRED")
    return row, user


def check_csrf(request, row):
    values = request.headers.getlist("x-csrf-token")
    if len(values) != 1 or not secrets.compare_digest(values[0].encode(), row.csrf_token.encode()):
        raise HTTPException(403, "CSRF_REJECTED")


def me_response(row, user):
    return MeResponse(user_id=user.id, username=user.username, role=user.role,
                      must_change_password=user.must_change_password, csrf_token=row.csrf_token)


def rate_rows(request, db, username):
    timestamp = request.app.state.clock()
    client = request.client.host if request.client else "unknown"
    rows = []
    for subject, limit in (("account:" + username.casefold(), 5), ("client:" + client, 20)):
        key = digest(subject)
        row = db.get(LoginAttempt, key)
        if row is None:
            row = LoginAttempt(subject_hash=key, window_start=timestamp, failures=0)
            db.add(row)
        elif timestamp >= row.window_start + 300:
            row.window_start, row.failures = timestamp, 0
        if row.failures >= limit:
            raise HTTPException(429, "LOGIN_RATE_LIMITED", headers={"Retry-After": "300"})
        rows.append(row)
    return rows


def verify(password, encoded):
    try:
        return password_hasher.verify(password, encoded)
    except (ValueError, TypeError):
        return False


@router.post("/auth/login", response_model=MeResponse, operation_id="login", tags=["auth"], dependencies=[Depends(load_cookie)])
def login(body: LoginInput, request: Request):
    denied = False
    with transaction(request) as db:
        attempts = rate_rows(request, db, body.username)
        user = db.scalar(select(User).where(User.username == body.username))
        matches = verify(body.password.get_secret_value(), user.password_hash if user else DUMMY_HASH)
        if user is None or not matches or not user.active:
            for attempt in attempts:
                attempt.failures += 1
            denied = True
        else:
            old_token = request.cookies.get(request.app.state.settings.cookie_name)
            if old_token:
                old = db.get(AuthSession, digest(old_token))
                if old and old.revoked_at is None:
                    old.revoked_at = request.app.state.clock()
            request.session.clear()
            token = regenerate_session_id(request)
            timestamp = request.app.state.clock()
            row = AuthSession(token_hash=digest(token), user_id=user.id, auth_version=user.auth_version,
                              csrf_token=secrets.token_hex(32), created_at=timestamp, last_seen=timestamp,
                              expires_at=timestamp + request.app.state.settings.absolute_seconds)
            db.add(row)
            request.session.update(user_id=user.id, auth_version=user.auth_version, csrf_token=row.csrf_token)
            result = me_response(row, user)
    if denied:
        raise HTTPException(401, "INVALID_CREDENTIALS")
    return result


@router.get("/auth/me", response_model=MeResponse, operation_id="get_me", tags=["auth"], dependencies=[Depends(load_cookie)])
def me(request: Request):
    with Session(request.app.state.engine) as db:
        row, user = principal(request, db)
        return me_response(row, user)


@router.post("/auth/logout", status_code=204, operation_id="logout", tags=["auth"], dependencies=[Depends(load_cookie)])
def logout(request: Request):
    with transaction(request) as db:
        row, _ = principal(request, db)
        check_csrf(request, row)
        row.revoked_at = request.app.state.clock()
    request.session.clear()
    return Response(status_code=204)


@router.post("/auth/password", status_code=204, operation_id="change_password", tags=["auth"], dependencies=[Depends(load_cookie)])
def password(body: PasswordInput, request: Request):
    denied = False
    with transaction(request) as db:
        row, user = principal(request, db)
        check_csrf(request, row)
        attempts = rate_rows(request, db, user.username)
        current, new = body.current_password.get_secret_value(), body.new_password.get_secret_value()
        if not verify(current, user.password_hash):
            for attempt in attempts:
                attempt.failures += 1
            denied = True
        else:
            if current == new:
                raise HTTPException(400, "PASSWORD_MUST_DIFFER")
            user.password_hash = password_hasher.hash(new)
            user.must_change_password = False
            user.auth_version += 1
            user.updated_at = now()
            db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                       .values(revoked_at=request.app.state.clock()))
    if denied:
        raise HTTPException(400, "CURRENT_PASSWORD_INCORRECT")
    request.session.clear()
    return Response(status_code=204)


@router.get("/admin/profiles", response_model=list[ProfileResponse], operation_id="get_profiles", tags=["admin"], dependencies=[Depends(load_cookie)])
def profiles(request: Request):
    with Session(request.app.state.engine) as db:
        principal(request, db, require_changed=True, admin=True)
        return [ProfileResponse(name=row.name, config_sha256=row.config_sha256, status=row.status)
                for row in db.scalars(select(PipelineProfile).order_by(PipelineProfile.name))]
