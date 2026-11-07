"""Real Uvicorn + production Next.js HTTP check using an isolated runtime DB.

Requires free ports 3000/8000 and an existing frontend build. Credentials and
cookies are generated in memory, never placed in command arguments or reports.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from backend.auth.settings import AuthSettings
from backend.db.connection import ROOT, make_engine
from backend.db.seed import seed
from scripts.migrate_database import migrate


def main():
    out = ROOT / "runtime/verification/r09"
    out.mkdir(parents=True, exist_ok=True)
    for port in (3000, 8000):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError("Required port occupied; no existing process will be stopped")
    evidence = {"date": "2026-11-07", "scope": "real Uvicorn and Next proxy; isolated DB; no real account password changes", "checks": []}
    processes, streams = [], []
    headers = {"Origin": "http://127.0.0.1:3000"}
    cookie_name = AuthSettings().cookie_name

    def record(name, passed):
        evidence["checks"].append({"name": name, "passed": bool(passed)})
        if not passed:
            raise AssertionError(name)  # no cookies/passwords in failures

    def launch(name, args, cwd, env):
        stream = (out / f"{name}-{len(processes)}.log").open("w", encoding="utf-8")
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)
        processes.append(process)
        streams.append(stream)
        return process

    def stop(process):
        if process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True, capture_output=True)
            process.wait(timeout=10)

    def ready(url):
        for _ in range(100):
            try:
                if httpx.get(url, timeout=2, trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise RuntimeError("Local service failed to start")

    with tempfile.TemporaryDirectory(prefix="r09-http-", dir=out) as temporary:
        path = Path(temporary) / "metadata.sqlite3"
        migrate(path)
        engine = make_engine(path)
        passwords = {name: secrets.token_urlsafe(24) for name in ("admin", "A", "B")}
        seed(engine, passwords.__getitem__)
        engine.dispose()
        env = {**os.environ, "LAYOUTPATCH_DATABASE_PATH": str(path), "APP_ORIGIN": headers["Origin"],
               "SESSION_COOKIE_SECURE": "false", "NEXT_TELEMETRY_DISABLED": "1"}
        backend_args = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"]
        try:
            backend = launch("backend", backend_args, ROOT, env)
            launch("frontend", [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], ROOT / "frontend", env)
            ready("http://127.0.0.1:8000/health")
            ready("http://127.0.0.1:3000/api/health")
            with httpx.Client(base_url="http://127.0.0.1:3000/api", timeout=10, trust_env=False) as proxy:
                def login(name):
                    return proxy.post("/auth/login", json={"username": name, "password": passwords[name]}, headers=headers)
                record("proxy_unauthenticated_401", proxy.get("/auth/me").status_code == 401)
                response = login("B")
                record("proxy_login_cookie", response.status_code == 200 and "httponly" in response.headers.get("set-cookie", "").lower())
                record("proxy_cookie_forwarded", proxy.get("/auth/me").status_code == 200)
                record("proxy_no_store", response.headers.get("cache-control") == "private, no-store")
                csrf = response.json()["csrf_token"]
                record("proxy_missing_csrf_403", proxy.post("/auth/logout", json={}, headers=headers).status_code == 403)
                record("proxy_cross_origin_403", proxy.post("/auth/logout", json={}, headers={"Origin": "http://evil.invalid", "X-CSRF-Token": csrf}).status_code == 403)
                record("proxy_first_password_gate_403", proxy.get("/admin/profiles").status_code == 403)
                old_cookie = proxy.cookies.get(cookie_name)
                new_password = secrets.token_urlsafe(24)
                changed = proxy.post("/auth/password", json={"current_password": passwords["B"], "new_password": new_password},
                                     headers={**headers, "X-CSRF-Token": csrf})
                record("proxy_password_change_and_cookie_clear", changed.status_code == 204 and proxy.cookies.get(cookie_name) is None)
                replay = httpx.get("http://127.0.0.1:8000/auth/me", headers={"Cookie": f"{cookie_name}={old_cookie}"}, trust_env=False)
                record("old_cookie_replay_direct_401", replay.status_code == 401)
                passwords["B"] = new_password
                response = login("B")
                record("new_password_login", response.status_code == 200 and not response.json()["must_change_password"])
                record("normal_user_role_403", proxy.get("/admin/profiles").status_code == 403)
                stop(backend)
                backend = launch("backend-restart", backend_args, ROOT, env)
                ready("http://127.0.0.1:8000/health")
                record("session_survives_real_backend_restart", proxy.get("/auth/me").status_code == 200)
                csrf = proxy.get("/auth/me").json()["csrf_token"]
                old_cookie = proxy.cookies.get(cookie_name)
                logged_out = proxy.post("/auth/logout", json={}, headers={**headers, "X-CSRF-Token": csrf})
                record("proxy_logout_clears_cookie", logged_out.status_code == 204 and proxy.cookies.get(cookie_name) is None)
                record("logout_replay_401", proxy.get("/auth/me", headers={"Cookie": f"{cookie_name}={old_cookie}"}).status_code == 401)
                response = login("admin")
                csrf = response.json()["csrf_token"]
                record("admin_password_gate_403", proxy.get("/admin/profiles").status_code == 403)
                admin_new_password = secrets.token_urlsafe(24)
                changed = proxy.post("/auth/password", json={"current_password": passwords["admin"], "new_password": admin_new_password},
                                     headers={**headers, "X-CSRF-Token": csrf})
                record("admin_password_change", changed.status_code == 204)
                passwords["admin"] = admin_new_password
                response = login("admin")
                profiles = proxy.get("/admin/profiles")
                record("admin_role_200_redacted", profiles.status_code == 200
                       and set(profiles.json()[0]) == {"name", "config_sha256", "status"})
            evidence["overall"] = "passed"
        finally:
            for process in processes:
                stop(process)
            for stream in streams:
                stream.close()
            (ROOT / "docs/checks/stage1b-3-http.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
