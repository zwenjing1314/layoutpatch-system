"""R17 isolated UI setup, reversible fixtures, process ownership and formal restoration."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
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

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.connection import DEFAULT_DATABASE, ROOT, make_engine
from backend.db.models import AuthSession, Document, PageFeature, User
from backend.db.seed import password_hasher
from backend.search.scope import active_index
from scripts.check_selection_http import dynamic_fingerprint
from scripts.check_stage1b_acceptance import process_records, vector_fingerprint
from scripts.check_stage2_preflight import snapshot
from scripts.migrate_database import migrate

OUT = ROOT / "runtime/verification/r17/ui"
STATE = OUT / "state.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def free(port):
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def prepare():
    OUT.mkdir(parents=True, exist_ok=False)
    source = ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3"
    baseline = {"source": snapshot(source)}
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src, closing(sqlite3.connect(OUT / "metadata.sqlite3")) as dst:
        src.backup(dst)
    migrate(OUT / "metadata.sqlite3")
    engine = make_engine(OUT / "metadata.sqlite3")
    passwords = {name: secrets.token_urlsafe(24) for name in ("A", "B", "admin")}
    with Session(engine) as db, db.begin():
        db.query(AuthSession).delete()
        for user in db.scalars(select(User)):
            user.password_hash = password_hasher.hash(passwords[user.username])
            user.must_change_password = user.username == "admin"
            user.auth_version += 1
            user.active = True
        index, _ = active_index(db)
        collection = index.collection_name
        documents = {doc.id: {"name": doc.display_name, "status": doc.status} for doc in db.scalars(select(Document))}
        a = db.scalar(select(User).where(User.username == "A"))
        for doc in db.scalars(select(Document).where(Document.owner_id == a.id)):
            doc.display_name = "R17_长文件名阅读检查_" + doc.display_name + "_完整页面视觉检索与硬件面积能耗比较.pdf"
        baseline["feature_files"] = {feature.tensor_path: hashlib.sha256((ROOT / feature.tensor_path).read_bytes()).hexdigest() for feature in db.scalars(select(PageFeature))}
    engine.dispose()
    baseline["collection"] = collection
    baseline["qdrant21"] = dynamic_fingerprint(collection, 21)
    write(OUT / "baseline.json", baseline)
    write(STATE, {"database": str(OUT / "metadata.sqlite3"), "passwords": passwords, "documents": documents, "owned": {}})
    print("Prepared isolated R17 clone, random test credentials and long-name metadata fixtures; source unchanged")


def start(name, formal=False):
    state = read(STATE)
    port = 8000 if name == "backend" else 3000
    if not free(port):
        raise RuntimeError("Port occupied; refusing to replace unknown process")
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("LAYOUTPATCH_") and ("AUDIT" in key or "UPLOAD" in key or "DATABASE" in key or "ACCEPTANCE" in key):
            env.pop(key)
    env.update(PYTHONUTF8="1", APP_ORIGIN="http://127.0.0.1:3000", SESSION_COOKIE_SECURE="false", NEXT_TELEMETRY_DISABLED="1")
    if name == "backend":
        module = "backend.main:app" if formal else "scripts.workspace_acceptance_server:app"
        env.update(LAYOUTPATCH_DATABASE_PATH=str(DEFAULT_DATABASE) if formal else state["database"], LAYOUTPATCH_INGEST_ENABLED="true" if formal else "false")
        if not formal:
            env.update(LAYOUTPATCH_WORKSPACE_ACCEPTANCE_DIR=str(OUT), LAYOUTPATCH_QUERY_AUDIT_DIR=str(OUT / "queries"), LAYOUTPATCH_PAGE_AUDIT_DIR=str(OUT / "page-audit"))
        args = [sys.executable, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--no-access-log"]
        cwd, url = ROOT, "http://127.0.0.1:8000/health"
    else:
        args = [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"]
        cwd, url = ROOT / "frontend", "http://127.0.0.1:3000"
    with (OUT / (name + "-" + str(time.time_ns()) + ".log")).open("wb") as log:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    info = process_records("ProcessId=" + str(proc.pid))[0]
    state["owned"][name] = {"pid": proc.pid, "created": info["Created"], "formal": formal}
    write(STATE, state)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2, trust_env=False).status_code == 200:
                print(f"Started {'formal' if formal else 'isolated'} {name}; port {port}; PID {proc.pid}")
                return
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError("Server exited; inspect private log")
        time.sleep(.2)
    raise RuntimeError("Startup timeout")


def stop(name):
    state = read(STATE)
    saved = state["owned"].get(name)
    if not saved:
        raise RuntimeError("No owned process to stop")
    records = process_records("ProcessId=" + str(saved["pid"]))
    if records:
        record = records[0]
        expected = "uvicorn" if name == "backend" else "node_modules/next/dist/bin/next"
        if record["Created"] != saved["created"] or expected not in record["CommandLine"]:
            raise RuntimeError("Process identity changed; refusing stop")
        subprocess.run(["taskkill", "/PID", str(saved["pid"]), "/T", "/F"], check=True, capture_output=True)
    state["owned"].pop(name)
    write(STATE, state)
    print("Stopped verified R17 " + name + " process tree")


def fixture(action):
    state = read(STATE)
    database = Path(state["database"]).resolve()
    if database != OUT / "metadata.sqlite3":
        raise RuntimeError("Fixture database must be the R17 private clone")
    engine = make_engine(database)
    if action == "revoke-A":
        change_account(engine, "A", "revoke", int(time.time()))
    elif action in ("empty-A", "restore-documents"):
        with Session(engine) as db, db.begin():
            a = db.scalar(select(User).where(User.username == "A"))
            for doc in db.scalars(select(Document)):
                if action == "empty-A" and doc.owner_id == a.id:
                    doc.status = "registered"
                elif action == "restore-documents":
                    doc.status = state["documents"][doc.id]["status"]
    elif action in ("fault-qdrant", "fault-scope", "delay-response"):
        target = OUT / action
        if target.exists():
            target.unlink()
        else:
            target.write_text("explicit R17 fixture", encoding="utf-8")
    else:
        raise ValueError("Unknown isolated fixture")
    engine.dispose()
    print("Applied isolated fixture: " + action)


def verify():
    report_path = ROOT / "docs/checks/stage2-3b1-formal.json"
    if report_path.exists():
        raise RuntimeError("Existing report; preserve and choose a new attempt")
    baseline = read(ROOT / "docs/checks/stage2-3b1-preflight.json")
    ui_baseline = read(OUT / "baseline.json")
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    check("formal_all_tables_and_schema_unchanged", snapshot(DEFAULT_DATABASE) == baseline["database"])
    check("formal_original13_full_vector_payload_config_unchanged", vector_fingerprint(baseline["collection"]) == baseline["qdrant"])
    check("reused21_full_vector_payload_config_unchanged", dynamic_fingerprint(ui_baseline["collection"], 21) == ui_baseline["qdrant21"])
    check("r15_source_database_logically_unchanged", snapshot(ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3") == ui_baseline["source"])
    check("eight_complete_feature_files_unchanged", len(ui_baseline["feature_files"]) == 8 and all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in ui_baseline["feature_files"].items()))
    protected = [path for path in baseline["files"] if path.startswith(("backend/", "migrations/", "frontend/lib/", "configs/")) or path in ("frontend/package.json", "frontend/yarn.lock", ".gitignore", "AGENTS.md") or path.startswith("requirements-") or path.startswith("docs/过程记录/0") and not path.startswith(("docs/过程记录/07_", "docs/过程记录/08_"))]
    check("backend_sdk_migrations_dependencies_and_history01_06_unchanged", all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == baseline["files"][path] for path in protected))
    with httpx.Client(base_url="http://127.0.0.1:3000", trust_env=False) as client:
        check("formal_next_home_200", client.get("/").status_code == 200)
        check("formal_health_200", client.get("/api/health").status_code == 200)
        for path in ("/api/auth/me", "/api/documents", "/api/search?q=anonymous-r17"):
            response = client.get(path)
            check("formal_anonymous_401_no_store_" + path.split("?")[0], response.status_code == 401 and response.headers.get("cache-control") == "private, no-store")
        response = client.post("/api/index", headers={"Origin": "http://untrusted.invalid"})
        check("upload_origin_protection_still_403", response.status_code == 403)
    check("no_page_encoding", not list((OUT / "page-audit").glob("*.json")))
    audits = [read(path) for path in (OUT / "queries").glob("*.json")]
    check("real_query_network_attempts_zero", bool(audits) and all(item["network_attempts"] == 0 for item in audits))
    write(report_path, {"date": datetime.now().astimezone().isoformat(), "round": "R17", "overall": "passed", "checks": checks, "query_count": len(audits), "query_model_pids": sorted({item["worker_pid"] for item in audits}), "page_encoding_count": 0, "formal_credentials_used_or_changed": False})
    print(f"Passed {len(checks)} restoration/protection checks; {len(audits)} real query forwards, zero page encoding")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "start", "stop", "fixture", "verify"))
    parser.add_argument("target", nargs="?")
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare": prepare()
    elif args.action == "start": start(args.target, args.formal)
    elif args.action == "stop": stop(args.target)
    elif args.action == "fixture": fixture(args.target)
    else: verify()
