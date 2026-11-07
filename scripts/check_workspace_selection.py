"""R18 isolated workspace-selection checks. Never uses formal credentials."""
from contextlib import closing
from datetime import datetime
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.connection import ROOT, DEFAULT_DATABASE, make_engine
from backend.db.models import AuthSession, Document, DocumentVersion, Job, PageFeature, User
from backend.db.seed import password_hasher
from backend.search.scope import active_index, allowed_scope
from scripts.check_selection_http import dynamic_fingerprint
from scripts.check_stage1b_acceptance import process_records
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate

OUT = ROOT / "runtime/verification/r18"
CHECKS = ROOT / "docs/checks"
UI = OUT / "ui"
STATE = UI / "state.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    OUT.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(OUT / "metadata-before.sqlite3")) as target:
        source.backup(target)
        collection = source.execute("SELECT collection_name FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)").fetchone()[0]
    paths = [p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/components", "frontend/lib", "frontend/tests", "configs", "docs")
             for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts]
    paths += [ROOT / name for name in (".gitignore", "AGENTS.md", "requirements-colpali.in", "requirements-colpali.lock.txt", "requirements-web.in", "requirements-web.lock.txt", "frontend/package.json", "frontend/yarn.lock")]
    raw = subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=ROOT).decode("utf-8")
    ports = subprocess.check_output(["powershell", "-NoProfile", "-Command", "Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 3000,8000,8001,6333 } | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress"], text=True, encoding="utf-8")
    report = {"date": datetime.now().astimezone().isoformat(), "round": "R18", "stage": "2-3B-2", "database": snapshot(DEFAULT_DATABASE),
              "collection": collection, "qdrant": vector_fingerprint(collection), "existing_changes": [line for line in raw.split("\0") if line],
              "files": {p.relative_to(ROOT).as_posix(): digest(p) for p in paths},
              "web_packages": sorted([d.metadata["Name"], d.version] for d in metadata.distributions()),
              "ports": json.loads(ports), "other_same_project_visible_chats": "idle or notLoaded; current chat is sole active visible project chat"}
    write(CHECKS / "stage2-3b2-preflight.json", report)
    print("R18 baseline/online backup saved; revision=" + report["database"]["revision"] + "; original pages=" + str(report["database"]["tables"]["pages"]["count"]))


def prepare():
    UI.mkdir(exist_ok=False)
    source = ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3"
    baseline = {"source": snapshot(source)}
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src, closing(sqlite3.connect(UI / "metadata.sqlite3")) as dst:
        src.backup(dst)
    migrate(UI / "metadata.sqlite3")
    engine = make_engine(UI / "metadata.sqlite3")
    passwords = {name: secrets.token_urlsafe(24) for name in ("A", "B", "admin")}
    ids = {}
    with Session(engine) as db, db.begin():
        db.query(AuthSession).delete()
        users = {user.username: user for user in db.scalars(select(User))}
        for user in users.values():
            user.password_hash = password_hasher.hash(passwords[user.username])
            user.must_change_password = user.username == "admin"
            user.auth_version += 1
            user.active = True
        for doc in db.scalars(select(Document)):
            version = db.get(DocumentVersion, doc.active_version_id)
            owner = next(name for name, user in users.items() if user.id == doc.owner_id)
            ids[f"{owner}{version.page_count}"] = doc.id
            if owner == "A":
                doc.display_name = "R18_同名_视觉文档完整页面检索_硬件面积能耗比较.pdf"
                doc.created_at = f"2026-11-08T00:0{2 if version.page_count == 5 else 1}:00Z"
            elif version.page_count == 4:
                doc.owner_id = users["admin"].id
                doc.visibility = "shared"
                doc.display_name = "R18_共享_中文_ＡＢＣ_100%_under_score.pdf"
                doc.created_at = "2026-11-08T00:00:00Z"
            else:
                doc.display_name = "R18_同名_视觉文档完整页面检索_硬件面积能耗比较.pdf"
        for n in range(12):
            doc = Document(source_key="r18-fixture-" + str(uuid4()), owner_id=users["A"].id,
                           display_name=f"R18_中文_待处理_{n:02d}_100%_under_score.pdf", visibility="private", status="registered", created_at=f"2026-11-07T12:00:{n:02d}Z")
            db.add(doc); db.flush()
            source_version = db.get(DocumentVersion, db.get(Document, ids["A5"]).active_version_id)
            version = DocumentVersion(document_id=doc.id, version=1, pdf_sha256=source_version.pdf_sha256, pdf_path=source_version.pdf_path,
                                      page_count=source_version.page_count, render_profile_json=source_version.render_profile_json, render_profile_sha256=source_version.render_profile_sha256)
            db.add(version); db.flush()
            db.add(Job(owner_id=users["A"].id, document_version_id=version.id, upload_key=str(uuid4()), request_sha256=source_version.pdf_sha256, upload_bytes=1,
                       status="failed" if n % 3 == 0 else "queued", stage="upload", error_code="INVALID_PDF" if n % 3 == 0 else None))
        index, _ = active_index(db)
        baseline["collection"] = index.collection_name
        baseline["feature_files"] = {feature.tensor_path: digest(ROOT / feature.tensor_path) for feature in db.scalars(select(PageFeature))}
        original = {doc.id: {key: getattr(doc, key) for key in ("display_name", "owner_id", "visibility", "status", "created_at")} for doc in db.scalars(select(Document))}
    engine.dispose()
    baseline["qdrant21"] = dynamic_fingerprint(baseline["collection"], 21)
    write(UI / "baseline.json", baseline)
    write(STATE, {"database": str(UI / "metadata.sqlite3"), "passwords": passwords, "ids": ids, "original": original, "owned": {}})
    print("R18 private clone prepared: real21 pages, A two ready documents, shared4, duplicate names and12 explicit unready metadata fixtures")


def start(name, formal=False):
    state = read(STATE)
    port = 8000 if name == "backend" else 3000
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("Port occupied; refusing replacement")
    env = {key: value for key, value in os.environ.items() if not key.startswith("LAYOUTPATCH_")}
    env.update(PYTHONUTF8="1", APP_ORIGIN="http://127.0.0.1:3000", SESSION_COOKIE_SECURE="false", NEXT_TELEMETRY_DISABLED="1")
    if name == "backend":
        env.update(LAYOUTPATCH_DATABASE_PATH=str(DEFAULT_DATABASE) if formal else state["database"], LAYOUTPATCH_INGEST_ENABLED="true" if formal else "false")
        if not formal:
            env.update(LAYOUTPATCH_R18_ACCEPTANCE_DIR=str(UI), LAYOUTPATCH_QUERY_AUDIT_DIR=str(UI / "queries"), LAYOUTPATCH_PAGE_AUDIT_DIR=str(UI / "page-audit"))
        args = [sys.executable, "-m", "uvicorn", "backend.main:app" if formal else "scripts.workspace_selection_server:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--no-access-log"]
        cwd, url = ROOT, "http://127.0.0.1:8000/health"
    else:
        args = [shutil.which("node"), "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"]
        cwd, url = ROOT / "frontend", "http://127.0.0.1:3000"
    with (UI / (name + "-" + str(time.time_ns()) + ".log")).open("wb") as log:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    info = process_records("ProcessId=" + str(proc.pid))[0]
    state["owned"][name] = {"pid": proc.pid, "created": info["Created"], "formal": formal}
    write(STATE, state)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, trust_env=False, timeout=2).status_code == 200:
                print(f"Started {'formal' if formal else 'isolated'} {name}; port{port}; launcher PID{proc.pid}")
                return
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError("Server exited; inspect private log")
        time.sleep(.2)
    raise RuntimeError("Startup timeout")


def stop(name, previous=False):
    state = read(STATE)
    saved = read(ROOT / "runtime/verification/r17/ui/state.json")["owned"].get(name) if previous else state["owned"].get(name)
    if not saved:
        raise RuntimeError("No recorded process ownership")
    records = process_records("ProcessId=" + str(saved["pid"]))
    if records:
        record = records[0]
        expected = "uvicorn" if name == "backend" else "node_modules/next/dist/bin/next"
        if record["Created"] != saved["created"] or expected not in record["CommandLine"]:
            raise RuntimeError("Process identity changed; refusing stop")
        subprocess.run(["taskkill", "/PID", str(saved["pid"]), "/T", "/F"], capture_output=True, check=True)
    if not previous:
        state["owned"].pop(name); write(STATE, state)
    print("Stopped verified " + ("previous formal " if previous else "R18 ") + name + " tree")


def fixture(action):
    state = read(STATE)
    if action in ("delay-list", "delay-search", "fault-qdrant"):
        target = UI / action
        if target.exists(): target.unlink()
        else: target.write_text("explicit R18 test fixture", encoding="utf-8")
    else:
        engine = make_engine(UI / "metadata.sqlite3")
        if action == "revoke-A":
            change_account(engine, "A", "revoke", int(time.time()))
        else:
            with Session(engine) as db, db.begin():
                if action == "unready-A5": db.get(Document, state["ids"]["A5"]).status = "registered"
                elif action == "withdraw-shared": db.get(Document, state["ids"]["B4"]).visibility = "private"
                elif action == "change-list": db.get(Document, state["ids"]["A4"]).display_name += "（变更）"
                elif action == "restore":
                    for key, values in state["original"].items():
                        doc = db.get(Document, key)
                        for name, value in values.items(): setattr(doc, name, value)
                else: raise ValueError("Unknown fixture")
        engine.dispose()
    print("Applied isolated fixture: " + action)


def api_basics():
    state, checks = read(STATE), []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition: raise AssertionError(name)
    with httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, timeout=20) as client:
        login = client.post("/auth/login", headers={"Origin": "http://127.0.0.1:3000"}, json={"username": "A", "password": state["passwords"]["A"]})
        check("isolated_A_login", login.status_code == 200)
        first = client.get("/documents", params={"limit": 10}).json()
        second = client.get("/documents", params={"limit": 10, "cursor": first["next_cursor"]}).json()
        check("real_authorized_cursor_pages_10_plus5", len(first["items"]) == 10 and len(second["items"]) == 5 and second["next_cursor"] is None)
        all_items = first["items"] + second["items"]
        check("two_own_ready_plus_one_shared_ready", sum(i["searchable"] for i in all_items) == 3 and sum(i["access"] == "shared" for i in all_items) == 1)
        check("twelve_explicit_unready_fixtures", sum(not i["searchable"] for i in all_items) == 12)
        check("B_private_same_name_not_in_A", state["ids"]["B8"] not in {i["document_id"] for i in all_items})
        for name, expected in (("同名", 2), ("abc", 1), ("ＡＢＣ", 1), ("中文", 13), ("%_", 13), ("％＿", 13), ("不存在-r18", 0)):
            response = client.get("/documents", params={"name": name, "limit": 50})
            check("authorized_filename_" + name, response.status_code == 200 and len(response.json()["items"]) == expected)
        for label, target in (("private", state["ids"]["B8"]), ("unknown", str(uuid4()))):
            response = client.get("/search", params={"q": "authorization-only-r18", "document_id": target})
            check(label + "_selection404_no_fallback", response.status_code == 404)
        unready = next(i["document_id"] for i in all_items if not i["searchable"])
        check("unready409_no_fallback", client.get("/search", params={"q": "unready-r18", "document_id": unready}).status_code == 409)
        check("list_operations_did_not_forward_model", not list((UI / "queries").glob("*.json")))
        write(UI / "expected-documents.json", {"items": all_items, "first_page": first["items"], "second_page": second["items"], "ids": state["ids"]})
    write(CHECKS / "stage2-3b2-http.json", {"date": datetime.now().astimezone().isoformat(), "round": "R18", "overall": "passed", "checks": checks, "note": "API baseline for browser comparison; metadata operations only, no query forward"})
    print(f"Passed {len(checks)} actual HTTP metadata/authorization checks; no model forward")


def verify():
    destination = CHECKS / "stage2-3b2-formal.json"
    if destination.exists(): raise RuntimeError("Preserve existing verification report")
    baseline, ui = read(CHECKS / "stage2-3b2-preflight.json"), read(UI / "baseline.json")
    state, checks = read(STATE), []
    def check(name, condition, **detail):
        checks.append({"name": name, "passed": bool(condition), **detail})
        if not condition:
            write(destination.with_stem(destination.stem + "-failed-" + str(time.time_ns())), {"overall": "failed", "checks": checks})
            raise AssertionError(name)
    check("formal_schema_all_tables_logically_unchanged", snapshot(DEFAULT_DATABASE) == baseline["database"])
    check("formal_original13_complete_vectors_payload_config_unchanged", vector_fingerprint(baseline["collection"]) == baseline["qdrant"])
    check("reused21_complete_vectors_payload_config_unchanged", dynamic_fingerprint(ui["collection"], 21) == ui["qdrant21"])
    check("r15_source_database_unchanged", snapshot(ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3") == ui["source"])
    check("all8_complete_BF16_feature_files_unchanged", len(ui["feature_files"]) == 8 and all(digest(ROOT / path) == sha for path, sha in ui["feature_files"].items()))
    protected = [path for path in baseline["files"] if path.startswith(("backend/", "migrations/", "configs/", "frontend/lib/api/")) or path in ("frontend/package.json", "frontend/yarn.lock", "frontend/app/globals.css", "frontend/lib/workspace-lifecycle.ts", ".gitignore", "AGENTS.md") or path.startswith("requirements-") or path.startswith("docs/过程记录/0") and not path.startswith(("docs/过程记录/07_", "docs/过程记录/08_"))]
    check("backend_SDK_migrations_algorithm_dependencies_login_and_history_unchanged", all(digest(ROOT / path) == baseline["files"][path] for path in protected), files=len(protected))
    check("preexisting_check_reports_unchanged", all(digest(ROOT / path) == sha for path, sha in baseline["files"].items() if path.startswith("docs/checks/")))
    with httpx.Client(base_url="http://127.0.0.1:3000", trust_env=False) as client:
        check("formal_next_home200", client.get("/").status_code == 200)
        check("formal_health200", client.get("/api/health").status_code == 200)
        for path in ("/api/auth/me", "/api/documents", "/api/search?q=anonymous-r18", "/api/search?q=anonymous-r18&document_id=" + state["ids"]["A5"]):
            response = client.get(path)
            check("formal_anonymous401_no_store_" + path.split("?")[0] + ("_selected" if "document_id" in path else ""), response.status_code == 401 and response.headers.get("cache-control") == "private, no-store" and "cookie" in response.headers.get("vary", "").lower())
        check("upload_Origin_guard_still403", client.post("/api/index", headers={"Origin": "http://untrusted.invalid"}).status_code == 403)
    check("zero_page_encoding", not list((UI / "page-audit").glob("*.json")))
    audits = [read(path) for path in (UI / "queries").glob("*.json")]
    check("new_queries_have_zero_network_attempts", bool(audits) and all(item["network_attempts"] == 0 for item in audits))
    pids = sorted({item["worker_pid"] for item in audits})
    check("isolated_model_processes_stopped", all(not process_records("ProcessId=" + str(pid)) for pid in pids))
    engine = make_engine(UI / "metadata.sqlite3")
    expected = {}
    with Session(engine) as db:
        users = {user.username: user for user in db.scalars(select(User))}
        for label, user, target in (("A_library13", users["A"], None), ("A_selected5", users["A"], state["ids"]["A5"]),
                                    ("A_selected4", users["A"], state["ids"]["A4"]), ("A_shared4", users["A"], state["ids"]["B4"]),
                                    ("B_library12", users["B"], None), ("B_selected8", users["B"], state["ids"]["B8"])):
            scope = allowed_scope(db, user, target)
            expected[label] = (frozenset(p.id for p in scope.pages), frozenset(p.version_id for p in scope.pages), scope.profile_id, scope.index_id)
    engine.dispose()
    filters = [json.loads(line) for line in (UI / "qdrant-filters.jsonl").read_text(encoding="utf-8").splitlines() if line]
    labels = []
    for item in filters:
        clauses = item["filter"]["must"]
        actual = (frozenset(next(c["has_id"] for c in clauses if "has_id" in c)),
                  frozenset(next(c["match"]["any"] for c in clauses if c.get("key") == "document_version_id")),
                  next(c["match"]["value"] for c in clauses if c.get("key") == "profile_id"),
                  next(c["match"]["value"] for c in clauses if c.get("key") == "index_generation"))
        labels.append(next((label for label, value in expected.items() if value == actual), "UNEXPECTED"))
    check("actual_Qdrant_filters_match_authorized_full_page_whitelists_before_TopK", len(filters) >= 5 and "UNEXPECTED" not in labels, observed_scopes=labels)
    events = [json.loads(line) for line in (UI / "http-observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    searches = [e for e in events if e["path"] == "/search"]
    check("real_HTTP_search_200_401_404_409_503_observed", {200, 401, 404, 409, 503} <= {e["status"] for e in searches})
    browser = read(UI / "browser-checks.json")
    check("all_recorded_browser_checks_passed", len(browser) >= 40 and all(item["passed"] for item in browser), count=len(browser))
    check("web_packages_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == baseline["web_packages"])
    report = {"date": datetime.now().astimezone().isoformat(), "round": "R18", "overall": "passed", "checks": checks,
              "query_count": len(audits), "query_worker_pids": pids, "page_encoding_count": 0, "formal_credentials_read_used_changed": False,
              "official_reference_rerun": False, "limits": ["frontend batch; no capacity or new official-score evaluation", "delays and metadata changes are explicit isolated fixtures", "old-repository protection is Git/selected files/dependencies, not ignored-file full audit"]}
    write(destination, report)
    print(f"Passed {len(checks)} actual formal restoration/protection checks; {len(audits)} query forwards; zero page encoding")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "prepare", "start", "stop", "fixture", "api-basics", "verify"))
    parser.add_argument("target", nargs="?")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--previous", action="store_true")
    args = parser.parse_args()
    if args.action == "preflight": preflight()
    elif args.action == "prepare": prepare()
    elif args.action == "start": start(args.target, args.formal)
    elif args.action == "stop": stop(args.target, args.previous)
    elif args.action == "api-basics": api_basics()
    elif args.action == "verify": verify()
    else: fixture(args.target)
