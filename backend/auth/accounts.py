"""Shared CLI/HTTP account lifecycle. All decisions occur under one SQLite write lock."""
from contextlib import contextmanager
import re

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.db.models import AccountEvent, AuthSession, User, now
from backend.db.seed import password_hasher


class AccountError(ValueError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


@contextmanager
def account_transaction(engine):
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                yield db
                db.flush()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def account_view(user):
    return dict(user_id=user.id, username=user.username, role=user.role, active=user.active,
                must_change_password=user.must_change_password, created_at=user.created_at, updated_at=user.updated_at)


def _password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise AccountError("INVALID_PASSWORD", 422)


def _execute(engine, action, target_ref, timestamp, operation, authorize):
    """authorize rechecks the current HTTP principal/CSRF AFTER acquiring the lock.

    CLI is a trusted local operator (null actor, explicit source). Authorized
    business rejections commit only an event; auth failures roll everything back.
    Unexpected DB/flush errors roll back the mutation AND its success event.
    """
    failure = None
    result = None
    with account_transaction(engine) as db:
        actor_id = authorize(db) if authorize else None
        try:
            user, changed = operation(db)
            result = dict(account=account_view(user), changed=changed)
            event = dict(target_id=user.id, outcome="success" if changed else "noop", code="OK")
        except AccountError as exc:
            failure = exc
            event = dict(target_id=None, outcome="rejected", code=exc.code)
        db.add(AccountEvent(actor_id=actor_id, source="http" if authorize else "cli", action=action,
                            target_ref=target_ref, occurred_at=timestamp, **event))
    if failure:
        raise failure
    return result


def create_account(engine, username, password, role, timestamp, *, authorize=None):
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username) or role not in ("user", "admin"):
        raise AccountError("INVALID_ACCOUNT", 422)
    _password(password)

    def operation(db):
        if db.scalar(select(User.id).where(User.username == username)):
            raise AccountError("USERNAME_EXISTS")
        user = User(username=username, password_hash=password_hasher.hash(password), role=role,
                    active=True, must_change_password=True, auth_version=1)
        db.add(user)
        db.flush()
        return user, True

    return _execute(engine, "create", username, timestamp, operation, authorize)


def change_account(engine, username, action, timestamp, password=None, *, user_id=None, authorize=None):
    if action not in ("disable", "enable", "revoke", "reset"):
        raise AccountError("INVALID_ACCOUNT_ACTION", 422)
    if action == "reset":
        _password(password)
    target = user_id if user_id is not None else username
    if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", target):
        raise AccountError("INVALID_ACCOUNT", 422)

    def operation(db):
        user = db.get(User, user_id) if user_id is not None else db.scalar(select(User).where(User.username == username))
        if user is None:
            raise AccountError("ACCOUNT_NOT_FOUND", 404)
        if action in ("enable", "disable") and user.active == (action == "enable"):
            return user, False
        if action == "disable" and user.role == "admin":
            count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.active.is_(True)))
            if count <= 1:
                raise AccountError("LAST_ACTIVE_ADMIN")
        user.auth_version += 1
        user.updated_at = now()
        if action in ("disable", "enable"):
            user.active = action == "enable"
        if action == "reset":
            user.password_hash = password_hasher.hash(password)
            user.must_change_password = True
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                   .values(revoked_at=timestamp))
        return user, True

    return _execute(engine, action, target, timestamp, operation, authorize)
