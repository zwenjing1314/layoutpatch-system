"""R15 isolated real upload/render/GPU/query/Qdrant lifecycle; no formal credentials."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import struct
import subprocess
import sys
import tarfile
import time

import httpx
from pypdf import PdfReader
from io import BytesIO
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import Document, DocumentVersion, IndexGeneration, Job, Page, PageFeature, User
from backend.db.seed import password_hasher, sha
from backend.search.qdrant import Qdrant
from backend.search.scope import active_index, allowed_scope
from scripts.migrate_database import migrate
from scripts.check_stage1b_acceptance import vector_fingerprint

ORIGIN = "http://127.0.0.1:3000"


def main(attempt):
    out = ROOT / f"runtime/verification/r15/real-attempt{attempt}"
    out.mkdir(parents=True, exist_ok=False)
    report_path = ROOT / f"docs/checks/stage2-2-http-attempt{attempt}.json"
    checks, process, log, cases = [], None, None, []
    engine = None

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
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

    def start(number):
        nonlocal process, log
        env = dict(os.environ)
        env.update(LAYOUTPATCH_DATABASE_PATH=str(out / "metadata.sqlite3"), LAYOUTPATCH_UPLOAD_ROOT=str(out / "uploads"),
                   LAYOUTPATCH_INGEST_ENABLED="true", LAYOUTPATCH_QUERY_AUDIT_DIR=str(out / "query-audit"),
                   LAYOUTPATCH_PAGE_AUDIT_DIR=str(out / "page-audit"), APP_ORIGIN=ORIGIN, SESSION_COOKIE_SECURE="false")
        log = (out / f"backend-{number}.log").open("wb")
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8001", "--workers", "1", "--no-access-log"],
                                   cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        limit = time.monotonic() + 30
        while time.monotonic() < limit:
            try:
                if httpx.get("http://127.0.0.1:8001/health", trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                raise RuntimeError("Isolated backend exited")
            time.sleep(.1)
        raise RuntimeError("Isolated backend start timeout")

    def login(client, name, password):
        r = client.post("/auth/login", json={"username": name, "password": password}, headers={"Origin": ORIGIN})
        check("isolated_login_" + name, r.status_code == 200)
        return r.json()["csrf_token"]

    def query(client, name, question, k=50):
        existing = set((out / "query-audit").glob("*.json"))
        response = client.get("/search", params={"q": question, "k": k})
        check("search_200_" + name, response.status_code == 200)
        body = response.json()
        fresh = set((out / "query-audit").glob("*.json")) - existing
        check("fresh_query_forward_" + name, len(fresh) == 1)
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.username == name.split("_")[0]))
            scope = allowed_scope(db, user)
            pages = {}
            for page in scope.pages:
                feature = db.get(PageFeature, page.id)
                pages[page.id] = {"tensor_path": feature.tensor_path} if feature else {"source_page_id": db.get(Page, page.id).source_page_id}
        cases.append({"name": name, "audit": str(next(iter(fresh))), "pages": pages, "items": body["items"], "k": k})
        check("all_returned_pages_authorized_" + name, {i["page_id"] for i in body["items"]} <= set(pages))
        return body

    try:
        with socket.socket() as probe:
            check("isolated_port_free", probe.connect_ex(("127.0.0.1", 8001)) != 0)
        with closing(sqlite3.connect(ROOT / "runtime/verification/r15/metadata-before.sqlite3")) as source, closing(sqlite3.connect(out / "metadata.sqlite3")) as target:
            source.backup(target)
        migrate(out / "metadata.sqlite3")
        engine = make_engine(out / "metadata.sqlite3")
        password = secrets.token_urlsafe(24)
        with Session(engine) as db, db.begin():
            for user in db.scalars(select(User)):
                user.password_hash, user.must_change_password = password_hasher.hash(password), False
            original_collection = active_index(db)[0].collection_name
            original_id = active_index(db)[0].id
        original_vectors = vector_fingerprint(original_collection)
        # New complete PDFs selected solely by archive filename/page count, no gold or question labels.
        manifest = json.loads((ROOT / "runtime/corpus/manifest.json").read_text())
        old_members = {d["archive_member"] for d in manifest["documents"]}
        chosen = []
        with tarfile.open(manifest["source_archive"], "r") as archive:
            for member in sorted((m for m in archive if m.isfile() and m.name.lower().endswith(".pdf") and m.name not in old_members), key=lambda m: m.name):
                data = archive.extractfile(member).read()
                try:
                    count = len(PdfReader(BytesIO(data)).pages)
                except Exception:
                    continue
                if 2 <= count <= 4:
                    destination = out / f"new-complete-{len(chosen)+1}.pdf"
                    destination.write_bytes(data)
                    chosen.append({"member": member.name, "path": str(destination), "sha256": sha(data), "pages": count})
                    if len(chosen) == 2:
                        break
        check("two_new_complete_pdfs_selected_without_gold", len(chosen) == 2)
        (out / "selected-pdfs.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
        start(1)
        with httpx.Client(base_url="http://127.0.0.1:8001", timeout=240, trust_env=False) as a, httpx.Client(base_url="http://127.0.0.1:8001", timeout=240, trust_env=False) as b:
            csrf_a, csrf_b = login(a, "A", password), login(b, "B", password)
            query(a, "A_before", "What hardware architecture and area results are discussed?")
            from uuid import uuid4
            jobs, during = [], []
            for client, csrf, document in ((a, csrf_a, chosen[0]), (b, csrf_b, chosen[1])):
                response = client.post("/index", files={"file": ("same-name.pdf", Path(document["path"]).read_bytes(), "application/pdf")}, headers={
                    "Origin": ORIGIN, "X-CSRF-Token": csrf, "X-Upload-ID": str(uuid4())})
                check("real_new_upload_202", response.status_code == 202)
                jobs.append(response.json())
            limit = time.monotonic() + 600
            while time.monotonic() < limit:
                states = [client.get("/jobs/" + job["job_id"]).json() for client, job in ((a, jobs[0]), (b, jobs[1]))]
                if any(s["status"] in ("failed", "interrupted") for s in states):
                    (out / "failed-job-states.json").write_text(json.dumps(states, indent=2), encoding="utf-8")
                    raise AssertionError("Real ingestion job failed; inspect fixed job code and private backend log")
                with Session(engine) as db:
                    current, _ = active_index(db)
                    # Validate metadata completeness at every observed activation.
                    for user in db.scalars(select(User)):
                        allowed_scope(db, user)
                    during.append({"index": current.id, "pages": current.page_count, "statuses": [s["status"] for s in states]})
                if all(s["status"] == "completed" for s in states):
                    break
                time.sleep(.5)
            else:
                raise AssertionError("Real ingestion exceeded 600s acceptance budget")
            check("both_real_jobs_completed", all(s["progress"] == 100 and s["attempt"] == 1 for s in states))
            body_a = query(a, "A_after", "What methods and experimental results are described in this paper?")
            body_b = query(b, "B_after", "What comparisons and conclusions are reported in the document?")
            repeat = query(a, "A_repeat", "What methods and experimental results are described in this paper?")
            check("repeat_query_is_new_forward", body_a["items"] == repeat["items"])
            new_a = {i["page_id"] for i in body_a["items"] if i["document_id"] == jobs[0]["document_id"]}
            new_b = {i["page_id"] for i in body_b["items"] if i["document_id"] == jobs[1]["document_id"]}
            check("all_new_pages_in_authorized_complete_scope", len(new_a) == chosen[0]["pages"] and len(new_b) == chosen[1]["pages"])
            check("cross_user_job_and_document_404", a.get("/jobs/" + jobs[1]["job_id"]).status_code == 404 and a.get("/documents/" + jobs[1]["document_id"]).status_code == 404)
            for client, other, body, new_pages in ((a, b, body_a, new_a), (b, a, body_b, new_b)):
                for hit in [i for i in body["items"] if i["page_id"] in new_pages]:
                    response = client.get(hit["preview_url"])
                    check("new_png_hash_and_private_headers", response.status_code == 200 and sha(response.content) == hit["render_sha256"] and response.headers.get("cache-control") == "private, no-store")
                    check("cross_user_new_png_404", other.get(hit["preview_url"]).status_code == 404)
            with Session(engine) as db:
                current, _ = active_index(db)
                check("dynamic_index_count_no_hardcoded13", current.page_count == 13 + sum(p["pages"] for p in chosen) and current.id != original_id)
                features = [{"page_id": f.page_id, "tensor_path": f.tensor_path, "tensor_sha256": f.tensor_sha256,
                             "export_path": f.export_path, "export_sha256": f.export_sha256} for f in db.scalars(select(PageFeature))]
                check("one_full_feature_artifact_per_new_page", len(features) == sum(p["pages"] for p in chosen))
                check("tensor_and_export_hashes", all(sha((ROOT/f["tensor_path"]).read_bytes()) == f["tensor_sha256"] and sha((ROOT/f["export_path"]).read_bytes()) == f["export_sha256"] for f in features))
                candidate_collections = [i.collection_name for i in db.scalars(select(IndexGeneration).where(IndexGeneration.id != original_id))]
            page_audits = [json.loads(p.read_text()) for p in (out / "page-audit").glob("*.json")]
            query_audits = [json.loads(p.read_text()) for p in (out / "query-audit").glob("*.json")]
            check("same_single_model_pid_for_page_and_query", len({v["worker_pid"] for v in page_audits + query_audits}) == 1)
            check("all_page_forwards_and_1024patch_contract", len(page_audits) == len(features) and all(v["patch_tokens"] == 1024 and v["token_count"] == 1031 and v["dimension"] == 128 for v in page_audits))
            check("network_attempts_zero", all(v["network_attempts"] == 0 for v in page_audits + query_audits))
            stop()
            start(2)
            persisted = a.get("/jobs/" + jobs[0]["job_id"]).json()
            check("completed_job_and_session_survive_restart", persisted["status"] == "completed")
            with Session(engine) as db:
                check("active_generation_survives_restart", active_index(db)[0].collection_name == current.collection_name)
            new_hit = next(i for i in body_a["items"] if i["page_id"] in new_a)
            check("new_png_survives_restart", a.get(new_hit["preview_url"]).status_code == 200)
        check("original_collection_all_bytes_payload_config_unchanged", vector_fingerprint(original_collection) == original_vectors)
        (out / "reference-cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "observed-states.json").write_text(json.dumps(during, indent=2), encoding="utf-8")
        report = {"date": "2026-11-07", "round": "R15", "stage": "2-2", "status": "passed", "checks": checks,
                  "input_pdfs": [{k:v for k,v in d.items() if k != "path"} for d in chosen], "new_full_page_count": len(features),
                  "new_collections": candidate_collections, "original_collection_unchanged": True,
                  "reference_cases": str(out / "reference-cases.json"), "artifacts": features,
                  "model_page_forwards": len(page_audits), "model_query_forwards_before_restart": len(query_audits),
                  "single_model_worker_pid": page_audits[0]["worker_pid"],
                  "limitations": ["new documents selected by filename/page count, not an accuracy benchmark", "no MinerU, D or highlighting", "copy-on-write small-corpus validation, not capacity test"]}
    except BaseException as exc:
        report = {"date": "2026-11-07", "round": "R15", "status": "failed", "error_type": type(exc).__name__, "checks": checks}
        raise
    finally:
        stop()
        if engine:
            engine.dispose()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R15 real ingestion: {len(checks)} checks passed; {len(features)} new pages, single model; stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.attempt <= 99:
        parser.error("attempt must be 1..99")
    main(args.attempt)
