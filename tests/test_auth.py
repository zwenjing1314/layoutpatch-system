"""HTTP authentication contracts against real migrated SQLite, with isolated random accounts."""
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.auth.settings import AuthSettings
from backend.auth.store import digest
from backend.db.connection import ROOT
from backend.db.models import AuthSession, User
from backend.db.seed import seed
from backend.main import create_app
from scripts.migrate_database import migrate

ORIGIN = "http://127.0.0.1:3000"


class AuthTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "runtime/verification").mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="r09-auth-", dir=ROOT / "runtime/verification")
        self.path = Path(self.temp.name) / "metadata.sqlite3"
        migrate(self.path)
        self.timestamp = time.time()
        self.settings = AuthSettings(database=self.path)
        self.app = create_app(self.settings, clock=lambda: self.timestamp)
        self.passwords = {name: secrets.token_urlsafe(24) for name in ("A", "B", "admin")}
        seed(self.app.state.engine, self.passwords.__getitem__)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.extra = []

    def tearDown(self):
        for client in self.extra:
            client.close()
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def other(self, app=None):
        client = TestClient(app or self.app)
        self.extra.append(client)
        return client

    def post(self, path, body=None, csrf=None, client=None, **kwargs):
        headers = {"Origin": ORIGIN}
        if csrf is not None:
            headers["X-CSRF-Token"] = csrf
        return (client or self.client).post(path, json=body if body is not None else {}, headers=headers, **kwargs)

    def login(self, name="A", client=None):
        response = self.post("/auth/login", {"username": name, "password": self.passwords[name]}, client=client)
        self.assertEqual(response.status_code, 200)
        return response

    def token(self, client=None):
        return (client or self.client).cookies.get(self.settings.cookie_name)

    def status(self, response, code):
        self.assertEqual(response.status_code, code)
        self.assertEqual(response.headers.get("cache-control"), "private, no-store")
        self.assertNotIn("access-control-allow-origin", response.headers)

    def change_password(self, name="A", client=None):
        csrf = self.login(name, client).json()["csrf_token"]
        new = secrets.token_urlsafe(24)
        self.status(self.post("/auth/password", {"current_password": self.passwords[name], "new_password": new},
                              csrf, client), 204)
        self.passwords[name] = new

    def test_unauthenticated_and_arbitrary_cookie_denied(self):
        self.status(self.client.get("/auth/me"), 401)
        self.status(self.client.get("/admin/profiles"), 401)
        self.client.cookies.set(self.settings.cookie_name, "a" * 32)
        self.status(self.client.get("/auth/me"), 401)
        self.status(self.post("/auth/logout", csrf="invalid"), 401)

    def test_origin_json_duplicate_origin_body_and_validation_secrets(self):
        body = {"username": "A", "password": self.passwords["A"]}
        for origin in (None, "null", "http://attacker.invalid", "http://127.0.0.1:8000"):
            headers = {} if origin is None else {"Origin": origin}
            self.status(self.client.post("/auth/login", json=body, headers=headers), 403)
        self.status(self.client.post("/auth/login", json=body,
                                    headers=[("Origin", ORIGIN), ("Origin", ORIGIN)]), 403)
        self.status(self.client.post("/auth/login", data=body, headers={"Origin": ORIGIN}), 415)
        self.status(self.client.post("/auth/login", json=body, headers={"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"}), 403)
        response = self.post("/auth/login", {**body, "role": "admin"})
        self.status(response, 422)
        self.assertTrue(self.passwords["A"] not in response.text)
        self.status(self.client.post("/auth/login", content=b"x" * 8193,
                                    headers={"Origin": ORIGIN, "Content-Type": "application/json"}), 413)

    def test_uniform_login_failure_and_persistent_rate_limit(self):
        wrong = self.post("/auth/login", {"username": "A", "password": "wrong"})
        missing = self.post("/auth/login", {"username": "missing", "password": "wrong"})
        self.status(wrong, 401)
        self.assertEqual(wrong.json(), missing.json())
        for _ in range(4):
            self.status(self.post("/auth/login", {"username": "a", "password": "wrong"}), 401)
        restarted = create_app(self.settings, clock=lambda: self.timestamp)
        try:
            client = self.other(restarted)
            self.status(self.post("/auth/login", {"username": "A", "password": self.passwords["A"]}, client=client), 429)
        finally:
            restarted.state.engine.dispose()
        self.timestamp += 301
        self.login()

    def test_cookie_flags_hash_storage_and_login_rotation(self):
        first = self.login()
        cookie = first.headers["set-cookie"].lower()
        for flag in ("httponly", "samesite=lax", "path=/", "max-age="):
            self.assertIn(flag, cookie)
        self.assertNotIn("domain=", cookie)
        self.assertNotIn("secure", cookie)
        old = self.token()
        self.login()
        self.assertTrue(self.token() != old)
        with Session(self.app.state.engine) as db:
            self.assertIsNotNone(db.get(AuthSession, digest(self.token())))
            self.assertIsNotNone(db.get(AuthSession, digest(old)).revoked_at)
        attacker = self.other()
        attacker.cookies.set(self.settings.cookie_name, old)
        self.status(attacker.get("/auth/me"), 401)
        with closing(sqlite3.connect(self.path)) as connection:
            dump = "\n".join(connection.iterdump())
            self.assertTrue(old not in dump and self.token() not in dump)
        self.status(self.client.get("/auth/me"), 200)

    def test_first_password_change_is_enforced_and_roles_are_real(self):
        self.login("admin")
        self.status(self.client.get("/admin/profiles"), 403)
        self.assertEqual(self.client.get("/admin/profiles").json()["detail"], "PASSWORD_CHANGE_REQUIRED")
        self.change_password("admin")
        self.login("admin")
        response = self.client.get("/admin/profiles")
        self.status(response, 200)
        self.assertEqual(set(response.json()[0]), {"name", "config_sha256", "status"})
        self.change_password("A")
        self.login("A")
        self.status(self.client.get("/admin/profiles"), 403)
        self.assertEqual(self.client.get("/admin/profiles").json()["detail"], "ADMIN_REQUIRED")

    def test_csrf_is_session_bound_and_rejects_missing_wrong_and_duplicate(self):
        csrf = self.login().json()["csrf_token"]
        other = self.other()
        other_csrf = self.login("B", other).json()["csrf_token"]
        for value in (None, "wrong", other_csrf):
            self.status(self.post("/auth/logout", csrf=value), 403)
        self.status(self.client.post("/auth/logout", json={}, headers=[("Origin", ORIGIN),
                                    ("X-CSRF-Token", csrf), ("X-CSRF-Token", csrf)]), 403)
        self.status(self.client.get("/auth/me"), 200)
        before = self.app.state.store.read_sync(self.token())
        self.status(self.post("/auth/password", {"current_password": self.passwords["A"],
                         "new_password": secrets.token_urlsafe(24)}, other_csrf), 403)
        self.assertTrue(before == self.app.state.store.read_sync(self.token()))
        self.status(self.client.post("/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf,
                                                             "Content-Type": "application/json"}), 204)

    def test_password_change_revokes_all_sessions_and_old_password(self):
        csrf = self.login().json()["csrf_token"]
        old_token = self.token()
        other = self.other()
        self.login("A", other)
        other_token = self.token(other)
        wrong = {"current_password": "wrong", "new_password": secrets.token_urlsafe(24)}
        self.status(self.post("/auth/password", wrong, csrf), 400)
        self.status(self.post("/auth/password", {"current_password": self.passwords["A"], "new_password": "short"}, csrf), 422)
        self.status(self.post("/auth/password", {"current_password": self.passwords["A"], "new_password": self.passwords["A"]}, csrf), 400)
        old_password = self.passwords["A"]
        new_password = secrets.token_urlsafe(24)
        self.status(self.post("/auth/password", {"current_password": old_password, "new_password": new_password}, csrf), 204)
        self.assertIsNone(self.token())
        for token in (old_token, other_token):
            client = self.other()
            client.cookies.set(self.settings.cookie_name, token)
            self.status(client.get("/auth/me"), 401)
        self.status(self.post("/auth/login", {"username": "A", "password": old_password}), 401)
        self.passwords["A"] = new_password
        response = self.login()
        self.assertFalse(response.json()["must_change_password"])

    def test_logout_revokes_copied_cookie_and_late_write_cannot_restore(self):
        csrf = self.login().json()["csrf_token"]
        token = self.token()
        stale_data = self.app.state.store.read_sync(token)
        self.status(self.post("/auth/logout", csrf=csrf), 204)
        self.assertIsNone(self.token())
        self.app.state.store.write_sync(token, stale_data)
        replay = self.other()
        replay.cookies.set(self.settings.cookie_name, token)
        self.status(replay.get("/auth/me"), 401)
        self.assertEqual(self.app.state.store.read_sync(token), b"")

    def test_expired_session_late_write_and_explicit_revoke_do_not_revive(self):
        self.login()
        token = self.token()
        stale_data = self.app.state.store.read_sync(token)
        self.timestamp += 1800
        self.app.state.store.write_sync(token, stale_data)
        self.status(self.client.get("/auth/me"), 401)
        self.login()
        change_account(self.app.state.engine, "A", "revoke", self.timestamp)
        self.status(self.client.get("/auth/me"), 401)
        self.login()

    def test_idle_and_absolute_expiry_with_injected_clock(self):
        self.login()
        self.timestamp += 1799
        self.status(self.client.get("/auth/me"), 200)
        self.timestamp += 1800
        self.status(self.client.get("/auth/me"), 401)
        self.login()
        for _ in range(28):
            self.timestamp += 1000
            self.status(self.client.get("/auth/me"), 200)
        self.timestamp += 800
        self.status(self.client.get("/auth/me"), 401)

    def test_disable_reenable_reset_version_and_role_changes_revoke_access(self):
        self.login()
        token = self.token()
        change_account(self.app.state.engine, "A", "disable", self.timestamp)
        self.status(self.client.get("/auth/me"), 401)
        denied = self.post("/auth/login", {"username": "A", "password": self.passwords["A"]})
        self.status(denied, 401)
        self.assertEqual(denied.json()["detail"], "INVALID_CREDENTIALS")
        change_account(self.app.state.engine, "A", "enable", self.timestamp)
        self.status(self.client.get("/auth/me"), 401)
        self.login()
        new_password = secrets.token_urlsafe(24)
        change_account(self.app.state.engine, "A", "reset", self.timestamp, new_password)
        self.status(self.client.get("/auth/me"), 401)
        self.passwords["A"] = new_password
        self.assertTrue(self.login().json()["must_change_password"])
        with self.app.state.engine.begin() as connection:
            connection.execute(text("UPDATE users SET auth_version=auth_version+1 WHERE username='A'"))
        self.status(self.client.get("/auth/me"), 401)
        self.change_password("admin")
        self.login("admin")
        with self.app.state.engine.begin() as connection:
            connection.execute(text("UPDATE users SET role='user' WHERE username='admin'"))
        self.status(self.client.get("/admin/profiles"), 403)

    def test_session_persists_across_application_recreation(self):
        self.login()
        token = self.token()
        restarted = create_app(self.settings, clock=lambda: self.timestamp)
        try:
            client = self.other(restarted)
            client.cookies.set(self.settings.cookie_name, token)
            self.status(client.get("/auth/me"), 200)
        finally:
            restarted.state.engine.dispose()

    def test_https_sets_secure_and_expected_routes(self):
        secure_app = create_app(AuthSettings(database=self.path, origin="https://localhost", secure=True))
        try:
            client = TestClient(secure_app, base_url="https://localhost")
            with client:
                result = client.post("/auth/login", json={"username": "A", "password": self.passwords["A"]},
                                     headers={"Origin": "https://localhost"})
                self.assertEqual(result.status_code, 200)
                self.assertIn("secure", result.headers["set-cookie"].lower())
        finally:
            secure_app.state.engine.dispose()
        self.assertEqual(set(self.app.openapi()["paths"]), {"/health", "/auth/login", "/auth/me", "/auth/password", "/auth/logout", "/admin/profiles", "/admin/documents", "/admin/documents/{document_id}/publish", "/admin/documents/{document_id}/unpublish", "/admin/users", "/admin/users/{user_id}", "/admin/users/{user_id}/password", "/admin/users/{user_id}/sessions/revoke", "/search", "/pages/{page_id}/image", "/index", "/jobs/{job_id}", "/documents/{document_id}", "/documents", "/jobs", "/jobs/{job_id}/retry", "/jobs/{job_id}/cancel", "/documents/{document_id}/parsing", "/pages/{page_id}/regions/status", "/pages/{page_id}/regions", "/pages/{page_id}/regions/{layout_id}/crop"})
        with self.assertRaises(ValueError):
            AuthSettings(database=self.path, origin="http://example.com")

    def test_database_failure_is_explicit_and_redacted(self):
        self.login()
        with self.app.state.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE auth_sessions")
        response = self.client.get("/auth/me")
        self.status(response, 503)
        self.assertEqual(response.json(), {"detail": "SERVICE_UNAVAILABLE"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
