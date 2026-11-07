"""Local account lifecycle used by an administrator CLI; no account-management HTTP routes."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.db.models import AuthSession, User, now
from backend.db.seed import password_hasher


def change_account(engine, username, action, timestamp, password=None):
    if action not in ("disable", "enable", "revoke", "reset"):
        raise ValueError("Unknown account action")
    if action == "reset" and (not isinstance(password, str) or not 12 <= len(password) <= 128):
        raise ValueError("Password must contain 12..128 characters")
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection) as db:
                user = db.scalar(select(User).where(User.username == username))
                if user is None:
                    raise ValueError("Unknown account")
                user.auth_version += 1
                user.updated_at = now()
                if action in ("disable", "enable"):
                    user.active = action == "enable"
                if action == "reset":
                    user.password_hash = password_hasher.hash(password)
                    user.must_change_password = True
                db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                           .values(revoked_at=timestamp))
                db.flush()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
