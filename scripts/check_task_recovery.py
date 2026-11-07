"""R19 isolated real PDF/UI environment and guarded local service ownership."""
import argparse
from contextlib import closing
from datetime import datetime
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
import tarfile
import time

import httpx
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import DEFAULT_DATABASE, ROOT, make_engine
from backend.db.models import AuthSession, User
from backend.db.seed import password_hasher, sha
from scripts.check_stage1b_acceptance import process_records
from scripts.check_stage2_preflight import snapshot
from scripts.check_selection_http import dynamic_fingerprint
from scripts.migrate_database import migrate

OUT = ROOT / "runtime/verification/r19"
UI = OUT / "ui"
STATE = UI / "state.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare():
    UI.mkdir(exist_ok=False)
    with closing(sqlite3.connect(OUT / "metadata-before.sqlite3")) as source, closing(sqlite3.connect(UI / "metadata.sqlite3")) as target:
        source.backup(target)
    migrate(UI / "metadata.sqlite3")
    engine = make_engine(UI / "metadata.sqlite3")
    passwords = {name: secrets.token_urlsafe(24) for name in ("A", "B", "admin")}
    with Session(engine) as db, db.begin():
        db.query(AuthSession).delete()
        for user in db.scalars(select(User)):
            user.password_hash = password_hasher.hash(passwords[user.username])
            user.must_change_password = user.username == "admin"
            user.active, user.auth_version = True, user.auth_version + 1
    engine.dispose()
    manifest = read(ROOT / "runtime/corpus/manifest.json")
    excluded = {doc["archive_member"] for doc in manifest["documents"]}
    excluded.update(doc["member"] for doc in read(ROOT / "runtime/verification/r15/real-attempt2/selected-pdfs.json"))
    chosen = []
    with tarfile.open(manifest["source_archive"], "r") as archive:
        for member in sorted((m for m in archive if m.isfile() and m.name.lower().endswith(".pdf") and m.name not in excluded), key=lambda m: m.name):
            data = archive.extractfile(member).read()
            try:
                count = len(PdfReader(BytesIO(data)).pages)
            except Exception:
                continue
            if 2 <= count <= 6:
                path = UI / f"new-complete-{len(chosen)+1}.pdf"
                path.write_bytes(data)
                chosen.append({"member": member.name, "path": str(path), "sha256": sha(data), "pages": count})
                if len(chosen) == 2:
                    break
    if len(chosen) != 2:
        raise RuntimeError("Need two new complete2-6 page PDFs; no model operation performed")
    write(UI / "selected-pdfs.json", chosen)
    prior = read(ROOT / "runtime/verification/r18/ui/baseline.json")
    write(UI / "prior-protection.json", {"r15_database": snapshot(ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3"),
        "features": prior["feature_files"], "collection": prior["collection"], "qdrant": dynamic_fingerprint(prior["collection"], 21)})
    write(STATE, {"database": str(UI / "metadata.sqlite3"), "passwords": passwords, "owned": {},
        "previous_owned": read(ROOT / "runtime/verification/r18/ui/state.json")["owned"]})
    print("R19 isolated original13 clone prepared; two distinct complete PDFs selected by name/page count, no gold; random credentials private")


def start(name, formal=False):
    state, port = read(STATE), 8000 if name == "backend" else 3000
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("Port occupied; refusing replacement")
    env = {key: value for key, value in os.environ.items() if not key.startswith("LAYOUTPATCH_")}
    env.update(PYTHONUTF8="1", APP_ORIGIN="http://127.0.0.1:3000", SESSION_COOKIE_SECURE="false", NEXT_TELEMETRY_DISABLED="1")
    if name == "backend":
        env.update(LAYOUTPATCH_DATABASE_PATH=str(DEFAULT_DATABASE) if formal else state["database"], LAYOUTPATCH_UPLOAD_ROOT=str(ROOT / "runtime/uploads") if formal else str(UI / "uploads"))
        if not formal:
            env.update(LAYOUTPATCH_R19_ACCEPTANCE_DIR=str(UI), LAYOUTPATCH_QUERY_AUDIT_DIR=str(UI / "queries"), LAYOUTPATCH_PAGE_AUDIT_DIR=str(UI / "pages"))
        args = [sys.executable, "-m", "uvicorn", "backend.main:app" if formal else "scripts.task_recovery_server:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--no-access-log"]
        cwd, url = ROOT, "http://127.0.0.1:8000/health"
    else:
        args = [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"]
        cwd, url = ROOT / "frontend", "http://127.0.0.1:3000"
    with (UI / (name + "-" + str(time.time_ns()) + ".log")).open("wb") as log:
        process = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    record = process_records("ProcessId=" + str(process.pid))[0]
    state["owned"][name] = {"pid": process.pid, "created": record["Created"], "formal": formal}
    write(STATE, state)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2, trust_env=False).status_code == 200:
                print(f"Started {'formal' if formal else 'isolated'} {name} port{port}, launcher PID{process.pid}")
                return
        except httpx.HTTPError:
            pass
        if process.poll() is not None:
            raise RuntimeError("Server exited; inspect private R19 log")
        time.sleep(.15)
    raise RuntimeError("Server startup timed out")


def stop(name, previous=False):
    state = read(STATE)
    saved = state["previous_owned" if previous else "owned"].get(name)
    if not saved:
        raise RuntimeError("No recorded process ownership")
    records = process_records("ProcessId=" + str(saved["pid"]))
    if records:
        record = records[0]
        expected = "uvicorn" if name == "backend" else "node_modules/next/dist/bin/next"
        if record["Created"] != saved["created"] or expected not in record["CommandLine"]:
            raise RuntimeError("Process identity changed; refusing stop")
        subprocess.run(["taskkill", "/PID", str(saved["pid"]), "/T", "/F"], check=True, capture_output=True)
    if not previous:
        state["owned"].pop(name)
        write(STATE, state)
    print("Stopped verified " + ("previous " if previous else "R19 ") + name + " tree")


def fixture(name):
    if name not in ("pause-claim", "hold-after-render", "hold-before-activation", "fail-render-once", "delay-upload-response"):
        raise ValueError("Unknown explicit fixture")
    path = UI / name
    if path.exists():
        path.unlink()
        print("Released R19 fixture: " + name)
    else:
        path.write_text("explicit R19 isolation-only fixture", encoding="utf-8")
        print("Enabled R19 fixture: " + name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "start", "stop", "fixture"))
    parser.add_argument("target", nargs="?")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--previous", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare": prepare()
    elif args.action == "start": start(args.target, args.formal)
    elif args.action == "stop": stop(args.target, args.previous)
    else: fixture(args.target)
