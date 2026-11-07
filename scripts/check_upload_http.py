"""R14 real HTTP and process restart acceptance. Isolated DB/files, no model calls."""
from contextlib import closing
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from pypdf import PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import Document, DocumentVersion, IndexGeneration, Job, User
from backend.db.seed import password_hasher, sha
from backend.search.scope import allowed_scope
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate

OUT = ROOT / "runtime/verification/r14/http"
REPORT = ROOT / "docs/checks/stage2-1-http.json"
ORIGIN = "http://127.0.0.1:3000"


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8001)) == 0:
            raise RuntimeError("Acceptance port already occupied")
    path = OUT / "metadata.sqlite3"
    with closing(sqlite3.connect(ROOT / "runtime/verification/r14/metadata-before.sqlite3")) as source, closing(sqlite3.connect(path)) as target:
        source.backup(target)
    migrate(path)
    engine = make_engine(path)
    password = secrets.token_urlsafe(24)
    results = []
    process = None
    log = None

    def check(name, condition):
        results.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    def stop():
        nonlocal process, log
        if process and process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=True)
            process.wait(timeout=15)
        process = None
        if log:
            log.close()
            log = None

    def start(attempt):
        nonlocal process, log
        environment = dict(os.environ)
        for key in ("LAYOUTPATCH_MODEL_AUDIT_DIR", "LAYOUTPATCH_QUERY_AUDIT_DIR"):
            environment.pop(key, None)
        environment.update(LAYOUTPATCH_DATABASE_PATH=str(path), LAYOUTPATCH_UPLOAD_ROOT=str(OUT / "uploads"),
                           LAYOUTPATCH_UPLOAD_MAX_BYTES="20971520", LAYOUTPATCH_UPLOAD_MAX_PAGES="100",
                           APP_ORIGIN=ORIGIN, SESSION_COOKIE_SECURE="false")
        log = (OUT / f"server-{attempt}.log").open("wb")
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
                                    "--port", "8001", "--workers", "1", "--no-access-log"], cwd=ROOT,
                                   env=environment, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Isolated backend exited")
            try:
                if httpx.get("http://127.0.0.1:8001/health", trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise RuntimeError("Isolated backend startup timed out")

    def pdf(width=200):
        writer = PdfWriter()
        writer.add_blank_page(width=width, height=300)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def login(client, name):
        r = client.post("/auth/login", json={"username": name, "password": password}, headers={"Origin": ORIGIN})
        check("isolated_login_" + name, r.status_code == 200)
        return r.json()["csrf_token"]

    def upload(client, csrf, key, data, **kw):
        return client.post("/index", files={"file": ("same.pdf", data, "application/pdf")},
                           headers={"Origin": ORIGIN, "X-CSRF-Token": csrf, "X-Upload-ID": key}, **kw)

    try:
        with Session(engine) as db, db.begin():
            # Only isolated clone credentials are changed; formal secrets are not read.
            for user in db.scalars(select(User)):
                user.password_hash, user.must_change_password = password_hasher.hash(password), False
            collection = db.scalar(select(IndexGeneration)).collection_name
            baseline_scopes = {u.username: allowed_scope(db, u).fingerprint for u in db.scalars(select(User))}
        before = vector_fingerprint(collection)
        start(1)
        with httpx.Client(base_url="http://127.0.0.1:8001", trust_env=False, timeout=30) as a, httpx.Client(
                base_url="http://127.0.0.1:8001", trust_env=False, timeout=30) as b:
            check("anonymous_upload_401", upload(a, "x", str(uuid4()), pdf()).status_code == 401)
            csrf_a, csrf_b = login(a, "A"), login(b, "B")
            key = str(uuid4())
            response_a = upload(a, csrf_a, key, pdf())
            response_b = upload(b, csrf_b, key, pdf(width=240))
            check("real_uploads_202", response_a.status_code == response_b.status_code == 202)
            job_a, job_b = response_a.json(), response_b.json()
            check("same_name_different_owner_distinct_identity", job_a["document_id"] != job_b["document_id"])
            check("queued_attempt_1", all(j["status"] == "queued" and j["attempt"] == 1 for j in (job_a, job_b)))
            check("idempotent_repeat", upload(a, csrf_a, key, pdf()).json() == job_a)
            check("key_conflict_409", upload(a, csrf_a, key, pdf(width=280)).status_code == 409)
            check("cross_owner_job_404", a.get("/jobs/" + job_b["job_id"]).status_code == 404)
            check("cross_owner_document_404", a.get("/documents/" + job_b["document_id"]).status_code == 404)
            check("own_document_registered_private", a.get("/documents/" + job_a["document_id"]).json()["status"] == "registered"
                  and a.get("/documents/" + job_a["document_id"]).json()["visibility"] == "private")
            check("foreign_origin_403", a.post("/index", files={"file": ("x.pdf", pdf(), "application/pdf")},
                  headers={"Origin": "https://attacker.invalid", "X-CSRF-Token": csrf_a}).status_code == 403)
            check("missing_csrf_403", a.post("/index", files={"file": ("x.pdf", pdf(), "application/pdf")},
                  headers={"Origin": ORIGIN}).status_code == 403)
            check("fake_pdf_422", upload(a, csrf_a, str(uuid4()), b"not-pdf").status_code == 422)
            check("no_store_headers", response_a.headers.get("cache-control") == "private, no-store" and response_a.headers.get("vary") == "Cookie")
            # Full configured 20MiB succeeds; over-limit file and request body reject.
            large = pdf()
            large += b" " * (20 * 1024 * 1024 - len(large))
            check("exact_20mib_pdf_202", upload(a, csrf_a, str(uuid4()), large).status_code == 202)
            check("over_file_limit_413", upload(a, csrf_a, str(uuid4()), large + b" ").status_code == 413)
            check("over_body_limit_413", a.post("/index", content=iter([b"x" * 1048576] * 21),
                  headers={"Origin": ORIGIN, "Content-Type": "multipart/form-data; boundary=test"}).status_code == 413)
            with Session(engine) as db:
                scopes_after = {u.username: allowed_scope(db, u).fingerprint for u in db.scalars(select(User))}
                check("all_13_page_search_scopes_unchanged", scopes_after == baseline_scopes)
                paths = [(ROOT / v.pdf_path, v.pdf_sha256) for v in db.scalars(select(DocumentVersion).join(
                    Document, Document.id == DocumentVersion.document_id).where(Document.source_key.like("upload:%")))]
            check("stored_bytes_match_hashes", all(sha(p.read_bytes()) == h for p, h in paths))
            # A valid PDF reaches a deliberately unavailable storage root, through real HTTP.
            moved = OUT / "uploads-preserved"
            (OUT / "uploads").rename(moved)
            (OUT / "uploads").write_bytes(b"blocked storage root")
            try:
                failed = upload(a, csrf_a, str(uuid4()), pdf())
                check("real_disk_failure_503", failed.status_code == 503)
                failed_id = failed.json()["job_id"]
                check("real_disk_failure_pollable", a.get("/jobs/" + failed_id).json()["error_code"] == "UPLOAD_WRITE_FAILED")
            finally:
                (OUT / "uploads").unlink()
                moved.rename(OUT / "uploads")
            # Simulate a crash reservation without inventing successful processing.
            interrupted = upload(a, csrf_a, str(uuid4()), pdf()).json()
            with Session(engine) as db, db.begin():
                db.get(Job, interrupted["job_id"]).status = "receiving"
            stop()
            start(2)
            check("cookie_and_queued_survive_real_restart", a.get("/jobs/" + job_a["job_id"]).json() == job_a)
            check("file_bytes_survive_real_restart", all(sha(p.read_bytes()) == h for p, h in paths))
            check("failed_job_survives_real_restart", a.get("/jobs/" + failed_id).json()["status"] == "failed")
            check("receiving_becomes_interrupted", a.get("/jobs/" + interrupted["job_id"]).json()["status"] == "interrupted")
            check("no_bare_pdf_route", a.get("/files/uploads/source.pdf").status_code == 404)
        check("qdrant_full_float32_payload_config_unchanged", vector_fingerprint(collection) == before)
        with closing(sqlite3.connect(path)) as db:
            check("sqlite_integrity_and_fk", db.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not db.execute("PRAGMA foreign_key_check").fetchall())
        report = {"date": "2026-11-07", "round": "R14", "stage": "2-1", "status": "passed", "checks": results,
                  "qdrant": before, "limitations": ["direct real HTTP on isolated port8001; no browser upload UI", "no page encoding, MinerU, D or GPU query",
                  "injected receiving reservation tests crash recovery; no OS power-cut test", "no retry/cancel endpoint in 2-1"]}
    except BaseException as exc:
        report = {"date": "2026-11-07", "round": "R14", "status": "failed", "error_type": type(exc).__name__, "checks": results}
        raise
    finally:
        stop()
        engine.dispose()
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R14 real HTTP/restart: {len(results)} checks passed; isolated process stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.attempt <= 99:
        parser.error("attempt must be 1..99")
    if args.attempt != 1:
        OUT = ROOT / f"runtime/verification/r14/http-attempt{args.attempt}"
        REPORT = ROOT / f"docs/checks/stage2-1-http-attempt{args.attempt}.json"
    main()
