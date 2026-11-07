"""starsessions adapter: opaque IDs only in cookies, SHA256 IDs in SQLite.

Only login can insert a session. Middleware writes can never recreate a revoked/deleted
row, preventing a late response from resurrecting an invalidated session.
"""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session
from starsessions.stores.base import SessionStore
from starlette.concurrency import run_in_threadpool

from backend.db.models import AuthSession, User


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SQLiteSessionStore(SessionStore):
    def __init__(self, engine, settings, clock):
        self.engine, self.settings, self.clock = engine, settings, clock

    def valid(self, row, user, timestamp):
        return (row is not None and user is not None and row.revoked_at is None and user.active
                and row.auth_version == user.auth_version and timestamp < row.expires_at
                and timestamp < row.last_seen + self.settings.idle_seconds)

    def read_sync(self, token):
        if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
            return b""
        with Session(self.engine) as session:
            row = session.get(AuthSession, digest(token))
            user = session.get(User, row.user_id) if row else None
            if not self.valid(row, user, self.clock()):
                return b""
            return json.dumps({"user_id": row.user_id, "auth_version": row.auth_version,
                               "csrf_token": row.csrf_token,
                               "__metadata__": {"created": row.created_at, "last_access": row.last_seen,
                                                "lifetime": self.settings.absolute_seconds}}).encode()

    async def read(self, session_id, lifetime):
        return await run_in_threadpool(self.read_sync, session_id)

    def write_sync(self, token, data):
        payload = json.loads(data)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection) as session:
                row = session.get(AuthSession, digest(token))
                user = session.get(User, row.user_id) if row else None
                timestamp = self.clock()
                if (self.valid(row, user, timestamp) and payload.get("user_id") == row.user_id
                        and payload.get("auth_version") == row.auth_version and payload.get("csrf_token") == row.csrf_token):
                    row.last_seen = max(row.last_seen, timestamp)
                    session.flush()
            connection.commit()
        return token

    async def write(self, session_id, data, lifetime, ttl):
        return await run_in_threadpool(self.write_sync, session_id, data)

    def remove_sync(self, token):
        with Session(self.engine) as session, session.begin():
            row = session.get(AuthSession, digest(token))
            if row and row.revoked_at is None:
                row.revoked_at = self.clock()

    async def remove(self, session_id):
        await run_in_threadpool(self.remove_sync, session_id)
