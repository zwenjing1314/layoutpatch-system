"""R19 checks against isolated random identities, then anonymous formal protection."""
from contextlib import closing
from datetime import datetime
import argparse
import importlib.metadata as metadata
import json
import sqlite3
import subprocess
from uuid import uuid4

import httpx

from backend.db.connection import DEFAULT_DATABASE, ROOT
from backend.main import app
from backend.db.connection import make_engine
from backend.db.models import Document, DocumentVersion, Job, User, new_id
from backend.documents.task_state import sync_attempt
from backend.db.seed import canonical, sha
from sqlalchemy import select
from sqlalchemy.orm import Session
from scripts.check_selection_http import dynamic_fingerprint
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.check_stage2_preflight import snapshot
from scripts.migrate_database import migrate
from scripts.check_task_recovery import UI, OUT, read, write

ORIGIN = "http://127.0.0.1:3000"


def pagination_fixture():
    path = UI / "pagination-fixture.json"
    if path.exists():
        raise RuntimeError("Pagination fixture already exists")
    engine = make_engine(UI / "metadata.sqlite3")
    ids = []
    with Session(engine) as db, db.begin():
        user = db.scalar(select(User).where(User.username == "B"))
        for number in range(10):
            doc_id, version_id = new_id(), new_id()
            label = "R19明确分页夹具-" + str(number + 1) + ("-很长的文件名" * 20 if number == 0 else "") + ".pdf"
            db.add(Document(id=doc_id, source_key="r19-pagination-fixture:" + doc_id, owner_id=user.id, display_name=label, visibility="private", status="registered", created_at="2000-01-01T00:00:00+00:00"))
            db.flush()
            pending = canonical({"status": "pending", "explicit_fixture": "R19 pagination only"})
            db.add(DocumentVersion(id=version_id, document_id=doc_id, version=1, pdf_sha256="0" * 64, pdf_path="runtime/verification/r19/ui/not-a-real-source-" + str(number), page_count=1, render_profile_json=pending, render_profile_sha256=sha(pending.encode())))
            db.flush()
            job = Job(id=new_id(), owner_id=user.id, document_version_id=version_id, upload_key=new_id(), request_sha256="0" * 64, upload_bytes=1, status="cancelled", error_code="CANCELLED_BY_OWNER", created_at="2000-01-01T00:00:00+00:00", updated_at="2000-01-01T00:00:00+00:00")
            db.add(job)
            db.flush()
            sync_attempt(db, job)
            ids.append(job.id)
    engine.dispose()
    write(path, {"purpose": "Explicit metadata-only pagination and long-name fixtures; no upload/render/encoding", "job_ids": ids})
    print("Added10 explicit cancelled pagination fixtures for B; no source or page encoding")


class Checks:
    def __init__(self, path):
        self.path, self.items = path, []
        if path.exists():
            raise RuntimeError("Evidence exists; preserve and choose another path")

    def check(self, name, condition):
        self.items.append({"name": name, "passed": bool(condition)})
        if not condition:
            self.save("failed")
            raise AssertionError(name)

    def save(self, status="passed", **extra):
        write(self.path, {"date": datetime.now().astimezone().isoformat(), "round": "R19", "stage": "2-3C", "overall": status, "checks": self.items, **extra})


def http_checks():
    state = read(UI / "state.json")
    c = Checks(ROOT / "docs/checks/stage2-3c-http.json")
    clients = {}
    try:
        for name in ("A", "B", "admin"):
            client = httpx.Client(base_url=ORIGIN + "/api", trust_env=False, timeout=30)
            clients[name] = client
            response = client.post("/auth/login", json={"username": name, "password": state["passwords"][name]}, headers={"Origin": ORIGIN})
            c.check(name + "_isolated_login", response.status_code == 200)
        csrf = {name: client.get("/auth/me").json()["csrf_token"] for name, client in clients.items()}
        jobs = {name: client.get("/jobs").json()["items"] for name, client in clients.items() if name != "admin"}
        c.check("A_B_lists_have_only_owned_real_task", len(jobs["A"]) >= 1 and len(jobs["B"]) >= 1 and not ({j["job_id"] for j in jobs["A"]} & {j["job_id"] for j in jobs["B"]}))
        c.check("first_change_admin_jobs_gate", clients["admin"].get("/jobs").status_code == 403)
        for owner, other in (("A", "B"), ("B", "A")):
            job = next(j for j in jobs[owner] if j["status"] == "completed")
            c.check(owner + "_completed_details_and_attempts", clients[owner].get("/jobs/" + job["job_id"]).json() == job and len(job["attempts"]) == (2 if owner == "A" else 3))
            c.check(other + "_cannot_get_" + owner + "_job", clients[other].get("/jobs/" + job["job_id"]).status_code == 404)
            for action in ("retry", "cancel"):
                path = "/jobs/" + job["job_id"] + "/" + action
                body = {"attempt": job["attempt"]}
                c.check(other + "_cannot_" + action + "_" + owner, clients[other].post(path, json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf[other]}).status_code == 404)
                c.check(owner + "_" + action + "_csrf_required", clients[owner].post(path, json=body, headers={"Origin": ORIGIN}).status_code == 403)
                c.check(owner + "_" + action + "_bad_origin", clients[owner].post(path, json=body, headers={"Origin": "https://bad.invalid", "X-CSRF-Token": csrf[owner]}).status_code == 403)
                c.check(owner + "_" + action + "_completed409", clients[owner].post(path, json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf[owner]}).status_code == 409)
                stale = clients[owner].post(path, json={"attempt": 1}, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf[owner]})
                c.check(owner + "_" + action + "_late_attempt409", stale.status_code == 409 and stale.json()["detail"] == "JOB_ATTEMPT_CHANGED")
            c.check(owner + "_unknown_query_rejected", clients[owner].get("/jobs?owner_id=other").status_code == 422)
            c.check(owner + "_duplicate_limit_rejected", clients[owner].get("/jobs?limit=1&limit=1").status_code == 422)
            c.check(owner + "_tampered_cursor_rejected", clients[owner].get("/jobs?cursor=bad").status_code == 422)
            doc = clients[owner].get("/documents/" + job["document_id"]).json()
            c.check(owner + "_ready_private_version1", doc["visibility"] == "private" and doc["status"] == "ready" and doc["version"] == 1)
            c.check(other + "_cannot_get_private_document", clients[other].get("/documents/" + job["document_id"]).status_code == 404)
        c.save(formal_credentials_used=False, limits=["No GPU query in this HTTP metadata pass; real browser query/PNG evidence recorded separately", "admin remains first-change locked; ordinary admin cross-user bypass checked in unit suite"])
        print(f"R19 HTTP: {len(c.items)} checks passed; isolated identities only")
    finally:
        for client in clients.values():
            client.close()


def formal_checks():
    c = Checks(ROOT / "docs/checks/stage2-3c-formal.json")
    baseline = read(ROOT / "docs/checks/stage2-3c-preflight.json")
    current = snapshot(DEFAULT_DATABASE)
    c.check("formal0007_integrity_ok_fk0", current["revision"] == "0007_job_attempts" and current["integrity"] == "ok" and current["foreign_key_errors"] == 0)
    c.check("only_job_attempts_table_added", set(current["tables"]) - set(baseline["database"]["tables"]) == {"job_attempts"})
    c.check("other_business_auth_tables_unchanged", all(current["tables"][t] == v for t, v in baseline["database"]["tables"].items() if t not in {"jobs", "alembic_version"}))
    with closing(sqlite3.connect(OUT / "metadata-before.sqlite3")) as old, closing(sqlite3.connect(DEFAULT_DATABASE)) as db:
        columns = [r[1] for r in old.execute("PRAGMA table_info(jobs)")]
        c.check("only_nullable_cancel_column_added_to_jobs", [r[1] for r in db.execute("PRAGMA table_info(jobs)")] == columns + ["cancel_requested_at"])
        projection = ",".join('"' + col + '"' for col in columns)
        c.check("original_job_columns_unchanged", old.execute("SELECT " + projection + " FROM jobs").fetchall() == db.execute("SELECT " + projection + " FROM jobs").fetchall())
    c.check("formal13_and_no_test_jobs_features_attempts", current["tables"]["pages"]["count"] == 13 and current["tables"]["documents"]["count"] == 2 and all(current["tables"][t]["count"] == 0 for t in ("jobs", "job_attempts", "page_features")))
    migrate(DEFAULT_DATABASE)
    c.check("repeat_migration_unchanged", snapshot(DEFAULT_DATABASE) == current)
    c.check("original_full_vectors_payload_config_unchanged", vector_fingerprint(baseline["collection"]) == baseline["qdrant"])
    prior = read(UI / "prior-protection.json")
    c.check("reused21_vectors_payload_config_unchanged", dynamic_fingerprint(prior["collection"], 21) == prior["qdrant"])
    c.check("R15_source_database_unchanged", snapshot(ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3") == prior["r15_database"])
    import hashlib
    c.check("old8_full_features_unchanged", all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == sha for p, sha in prior["features"].items()))
    c.check("OpenAPI_current", app.openapi() == read(ROOT / "frontend/docs/openapi.json"))
    c.check("web_dependencies_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == baseline["web_packages"])
    with httpx.Client(base_url=ORIGIN, timeout=30, trust_env=False) as client:
        c.check("formal_home_health200", client.get("/").status_code == client.get("/api/health").status_code == 200)
        for path in ("/api/auth/me", "/api/jobs", "/api/jobs/unknown", "/api/documents", "/api/search?q=r19", "/api/pages/unknown/image"):
            response = client.get(path)
            c.check("anonymous401_no_store_" + path.split("?")[0], response.status_code == 401 and response.headers.get("cache-control") == "private, no-store" and "cookie" in response.headers.get("vary", "").lower())
        for path in ("/api/index", "/api/jobs/unknown/retry", "/api/jobs/unknown/cancel"):
            payload = {"files": {"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")}} if path == "/api/index" else {"json": {"attempt": 1}}
            c.check("bad_origin403_" + path, client.post(path, **payload, headers={"Origin": "https://bad.invalid"}).status_code == 403)
            c.check("same_origin_anonymous401_" + path, client.post(path, **payload, headers={"Origin": ORIGIN}).status_code == 401)
    c.check("anonymous_checks_do_not_change_formal_rows", snapshot(DEFAULT_DATABASE) == current)
    def ps(command):
        value = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True).strip()
        return json.loads(value) if value else []
    ports = ps("@(Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess) | ConvertTo-Json -Compress")
    c.check("formal_ports_restored_8001_free", {p["LocalPort"] for p in ports} == {3000, 8000, 6333})
    workers = ps("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scripts/model_query_worker.py*' } | Select-Object ProcessId) | ConvertTo-Json -Compress")
    c.check("test_model_tree_stopped", not workers)
    c.save(database=current, ports=ports, formal_credentials_read_used_changed=False, limits=["Formal HTTP anonymous only; real new PDF checks use isolated clone", "Old-project audit covers Git/selected files/model dependencies, not every ignored file"])
    print(f"R19 formal: {len(c.items)} checks passed; additive0007 and original13 protected")


def runtime_checks():
    c = Checks(ROOT / "docs/checks/stage2-3c-runtime.json")
    events = [json.loads(line) for line in (UI / "http-observations.jsonl").read_text(encoding="utf-8").splitlines()]
    searches = [e["response"] for e in events if e["path"] == "/search" and e["status"] == 200]
    filters = [json.loads(line) for line in (UI / "qdrant-filters.jsonl").read_text(encoding="utf-8").splitlines()]
    pages = [read(p) for p in (UI / "pages").glob("*.json")]
    queries = [read(p) for p in (UI / "queries").glob("*.json")]
    c.check("four_real_successful_queries_and_filters", len(searches) == len(filters) == len(queries) == 4)
    c.check("scopes_filtered_before_top_k", [len(next(row["has_id"] for row in f["filter"]["must"] if "has_id" in row)) for f in filters] == [5, 10, 6, 14])
    for i, (body, f) in enumerate(zip(searches, filters, strict=True)):
        allowed = set(next(row["has_id"] for row in f["filter"]["must"] if "has_id" in row))
        c.check("authorized_real_top3_" + str(i + 1), len(body["items"]) == 3 and all(hit["page_id"] in allowed for hit in body["items"]) and [hit["page_number"] for hit in body["items"]] == ([1, 3, 5] if i < 2 else [1, 4, 2]))
    c.check("four_authorized_PNG_responses", sum(e["path"].startswith("/pages/") and e["status"] == 200 for e in events) == 4)
    c.check("actual16_page_forwards_and_two_sequential_workers", len(pages) == 16 and len({r["worker_pid"] for r in pages + queries}) == 2 and all(r["network_attempts"] == 0 for r in pages + queries))
    with closing(sqlite3.connect(UI / "metadata.sqlite3")) as db:
        db.row_factory = sqlite3.Row
        jobs = [dict(row) for row in db.execute("SELECT j.*,u.username FROM jobs j JOIN users u ON j.owner_id=u.id WHERE j.created_at>'2001'")]
        c.check("three_real_jobs_not_four_after_same_key_resend", len(jobs) == 3 and sorted(j["status"] for j in jobs) == ["cancelled", "completed", "completed"])
        for user, expected in (("A", ["cancelled", "completed"]), ("B", ["failed", "interrupted", "completed"])):
            job = next(j for j in jobs if j["username"] == user and j["status"] == "completed")
            statuses = [r[0] for r in db.execute("SELECT status FROM job_attempts WHERE job_id=? ORDER BY attempt", (job["id"],))]
            c.check(user + "_attempts_retained_same_job_version", statuses == expected)
            c.check(user + "_version_only_one_page_set", db.execute("SELECT count(*) FROM pages WHERE document_version_id=?", (job["document_version_id"],)).fetchone()[0] == (5 if user == "A" else 6))
        cancelled = next(j for j in jobs if j["status"] == "cancelled")
        c.check("queued_cancellation_has_no_page_features", db.execute("SELECT count(*) FROM pages WHERE document_version_id=?", (cancelled["document_version_id"],)).fetchone()[0] == 0)
        c.check("active24_full_pages_11_new_features", db.execute("SELECT count(*) FROM pages").fetchone()[0] == 24 and db.execute("SELECT count(*) FROM page_features").fetchone()[0] == 11)
        c.check("failed_candidate_preserved", db.execute("SELECT count(*) FROM index_generations WHERE status='failed'").fetchone()[0] == 1)
    uploads = [e for e in events if e["path"] == "/index" and e["status"] == 202 and isinstance(e.get("response"), dict)]
    c.check("four_accepted_upload_responses_three_job_ids", len(uploads) == 4 and len({e["response"]["job_id"] for e in uploads}) == 3)
    c.check("invalid_PDF422_observed", any(e["path"] == "/index" and e["status"] == 422 for e in events))
    c.check("formal_database_not_touched_by_isolated_checks", snapshot(DEFAULT_DATABASE) == read(ROOT / "docs/checks/stage2-3c-preflight.json")["database"])
    for flag in ("pause-claim", "hold-after-render", "hold-before-activation", "fail-render-once", "delay-upload-response"):
        c.check("fixture_released_" + flag, not (UI / flag).exists())
    state = read(UI / "state.json")
    with httpx.Client(base_url=ORIGIN + "/api", trust_env=False, timeout=30) as client:
        for i, name in enumerate(("B", "A")):
            response = client.post("/auth/login", json={"username": name, "password": state["passwords"][name]}, headers={"Origin": ORIGIN})
            c.check(name + "_isolated_cross_object_login", response.status_code == 200)
            target = searches[0 if i == 0 else 2]
            c.check(name + "_cross_document404_before_query", client.get("/search", params={"q": "R19 unauthorized target", "document_id": target["document_id"]}).status_code == 404)
            c.check(name + "_cross_session_private_PNG404", client.get(target["items"][0]["preview_url"]).status_code == 404)
    c.save(actual_page_forwards=16, actual_query_forwards=4, worker_pids=sorted({r["worker_pid"] for r in pages + queries}), network_attempts=0, successful_query_cases=[{"mode": b["search_mode"], "document_id": b["document_id"], "page_numbers": [h["page_number"] for h in b["items"]], "page_scores": [h["page_score"] for h in b["items"]]} for b in searches], limits=["Five page forwards are cancelled-attempt cost;11 features activated", "Two model trees were sequential because the backend was actually stopped/restarted", "Render failure and gate/8-second response delays are explicit isolated fixtures; hard backend stop was real", "Ten cancelled metadata-only jobs exist solely for UI pagination/long names", "Cross-session PNG404 does not isolate signature versus object-authorization rejection", "No official scoring/accuracy/capacity/GPU-operator-interruption/BFCache rerun"])
    print(f"R19 runtime: {len(c.items)} checks passed;16 page +4 query forwards; no network")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("http", "formal", "pagination", "runtime"))
    args = parser.parse_args()
    {"http": http_checks, "formal": formal_checks, "pagination": pagination_fixture, "runtime": runtime_checks}[args.action]()
