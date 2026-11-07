"""R16 real selected-document queries; reuse existing21 pages, no re-encoding or vector writes."""
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
import time
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, make_engine
from backend.db.models import AuthSession, Document, DocumentVersion, Job, Page, PageFeature, User
from backend.db.seed import password_hasher, sha
from backend.search.scope import active_index, allowed_scope
from backend.search.qdrant import Qdrant
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate

ORIGIN = "http://127.0.0.1:3000"


def dynamic_fingerprint(collection, expected_count):
    qdrant = Qdrant()
    info = qdrant.info(collection)
    qdrant.check_info(info, expected_count)
    points = sorted(qdrant.all_points(collection), key=lambda p: str(p["id"]))
    if len(points) != expected_count:
        raise AssertionError("Incomplete collection")
    rows = []
    for point in points:
        vectors = point["vector"]["original"]
        if len(vectors) != 1031 or any(len(v) != 128 for v in vectors):
            raise AssertionError("Incomplete full feature")
        digest = hashlib.sha256()
        for vector in vectors: digest.update(struct.pack("<128f", *vector))
        rows.append({"id": point["id"], "payload": point["payload"], "float32_sha256": digest.hexdigest()})
    return {"point_count": len(points), "sha256": sha(json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()), "config": info["config"]}


def main(attempt):
    out = ROOT / f"runtime/verification/r16/real-attempt{attempt}"
    out.mkdir(parents=True, exist_ok=False)
    report_path = ROOT / f"docs/checks/stage2-3a-http-attempt{attempt}.json"
    if report_path.exists():
        raise RuntimeError("Report exists; never overwrite previous attempts")
    checks, cases, process, log, engine = [], [], None, None, None

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
            log.close(); log = None

    def start(number):
        nonlocal process, log
        env = dict(os.environ)
        env.update(LAYOUTPATCH_DATABASE_PATH=str(out / "metadata.sqlite3"), LAYOUTPATCH_INGEST_ENABLED="false",
                   LAYOUTPATCH_QUERY_AUDIT_DIR=str(out / "query-audit"), LAYOUTPATCH_PAGE_AUDIT_DIR=str(out / "page-audit"),
                   LAYOUTPATCH_SELECTION_AUDIT_DIR=str(out / "filter-audit"), APP_ORIGIN=ORIGIN, SESSION_COOKIE_SECURE="false")
        log = (out / f"backend-{number}.log").open("wb")
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "scripts.selection_acceptance_server:app", "--host", "127.0.0.1",
                                    "--port", "8001", "--workers", "1", "--no-access-log"], cwd=ROOT, env=env, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get("http://127.0.0.1:8001/health", trust_env=False).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if process.poll() is not None:
                raise RuntimeError("Isolated server exited; inspect private log")
            time.sleep(.1)
        raise RuntimeError("Server start timeout")

    def login(client, name, password):
        response = client.post("/auth/login", json={"username": name, "password": password}, headers={"Origin": ORIGIN})
        check("isolated_login_" + name, response.status_code == 200)

    def request(client, path, status=200, **kwargs):
        response = client.get(path, **kwargs)
        check("private_HTTP_" + str(status) + "_" + path.split("?")[0], response.status_code == status and response.headers.get("cache-control") == "private, no-store")
        return response

    def query(client, name, question, target=None, k=50):
        old_queries = set((out / "query-audit").glob("*.json"))
        old_filters = set((out / "filter-audit").glob("*.json"))
        params = {"q": question, "k": k, **({"document_id": target} if target else {})}
        body = request(client, "/search", params=params).json()
        fresh_query = set((out / "query-audit").glob("*.json")) - old_queries
        fresh_filter = set((out / "filter-audit").glob("*.json")) - old_filters
        check("new_real_query_and_filter_" + name, len(fresh_query) == len(fresh_filter) == 1)
        with Session(engine) as db:
            user = db.scalar(select(User).where(User.username == name.split("_")[0]))
            scope = allowed_scope(db, user, target)
            pages = {}
            for page in scope.pages:
                feature = db.get(PageFeature, page.id)
                pages[page.id] = {"tensor_path": feature.tensor_path} if feature else {"source_page_id": db.get(Page, page.id).source_page_id}
            check("full_index_count_21_" + name, scope.index_page_count == 21)
        filter_body = json.loads(next(iter(fresh_filter)).read_text(encoding="utf-8"))
        must = filter_body["filter"]["must"]
        check("actual_filter_before_topk_" + name, set(next(v["has_id"] for v in must if "has_id" in v)) == set(pages)
              and next(v["match"]["any"] for v in must if v.get("key") == "document_version_id") == sorted({p.version_id for p in scope.pages})
              and filter_body["params"] == {"exact": True} and filter_body["limit"] == k)
        check("response_scope_" + name, body["search_mode"] == ("document" if target else "library") and body["document_id"] == target
              and len(body["items"]) == min(k, len(pages)) and {i["page_id"] for i in body["items"]} <= set(pages))
        cases.append({"name": name, "audit": str(next(iter(fresh_query))), "filter_audit": str(next(iter(fresh_filter))),
                      "pages": pages, "items": body["items"], "k": k, "target_document_id": target})
        return body

    try:
        with socket.socket() as probe:
            check("isolated_port_free", probe.connect_ex(("127.0.0.1", 8001)) != 0)
        source_path = ROOT / "runtime/verification/r15/real-attempt2/metadata.sqlite3"
        source_before = snapshot(source_path)
        with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(out / "metadata.sqlite3")) as target:
            source.backup(target)
        migrate(out / "metadata.sqlite3")
        engine = make_engine(out / "metadata.sqlite3")
        password = secrets.token_urlsafe(24)
        with Session(engine) as db, db.begin():
            db.query(AuthSession).delete()
            for user in db.scalars(select(User)):
                user.password_hash, user.must_change_password = password_hasher.hash(password), False
                user.auth_version += 1
            index, _ = active_index(db)
            active_collection = index.collection_name
            check("reuse_completed21_page_index", index.page_count == 21)
            users = {u.username: u.id for u in db.scalars(select(User))}
            documents = list(db.scalars(select(Document).where(Document.status == "ready")))
            a_docs = [d for d in documents if d.owner_id == users["A"]]
            b_docs = [d for d in documents if d.owner_id == users["B"]]
            check("two_ready_documents_per_user", len(a_docs) == len(b_docs) == 2)
            new_a = next(d.id for d in a_docs if d.source_key.startswith("upload:"))
            old_a = next(d.id for d in a_docs if not d.source_key.startswith("upload:"))
            new_b = next(d.id for d in b_docs if d.source_key.startswith("upload:"))
            old_b = next(d.id for d in b_docs if not d.source_key.startswith("upload:"))
            template = db.get(DocumentVersion, db.get(Document, old_a).active_version_id)
            fixture_ids = {}
            for number, (name, owner, state) in enumerate([
                    ("ＡＢＣ中文_100%.pdf", "A", "queued"), ("Straße.pdf", "A", "failed"),
                    ("中文报告.pdf", "A", "failed"), ("同名.pdf", "A", "failed"), ("同名.pdf", "B", "failed")]):
                doc = Document(source_key=f"r16-metadata:{number}", owner_id=users[owner], display_name=name, status="registered", visibility="private")
                db.add(doc); db.flush()
                version = DocumentVersion(document_id=doc.id, version=1, pdf_sha256=template.pdf_sha256, pdf_path=template.pdf_path,
                    page_count=template.page_count, render_profile_json=template.render_profile_json, render_profile_sha256=template.render_profile_sha256)
                db.add(version); db.flush()
                db.add(Job(owner_id=users[owner], document_version_id=version.id, upload_key=str(uuid4()), request_sha256="e"*64,
                           upload_bytes=100, status=state, stage="queued", error_code="PAGE_ENCODING_FAILED" if state == "failed" else None))
                fixture_ids[(owner, name)] = doc.id
        active_before = dynamic_fingerprint(active_collection, 21)
        original = json.loads((ROOT / "docs/checks/stage2-3a-preflight.json").read_text(encoding="utf-8"))
        with Session(engine) as db:
            feature_hashes = {f.tensor_path: sha((ROOT / f.tensor_path).read_bytes()) for f in db.scalars(select(PageFeature))}
        start(1)
        with httpx.Client(base_url="http://127.0.0.1:8001", timeout=240, trust_env=False) as a, httpx.Client(base_url="http://127.0.0.1:8001", timeout=240, trust_env=False) as b, httpx.Client(base_url="http://127.0.0.1:8001", timeout=240, trust_env=False) as admin:
            request(a, "/documents", 401)
            login(a, "A", password); login(b, "B", password); login(admin, "admin", password)
            for term, expected in [("abc", "ＡＢＣ中文_100%.pdf"), ("ａｂｃ", "ＡＢＣ中文_100%.pdf"), ("%", "ＡＢＣ中文_100%.pdf"),
                                   ("_", "ＡＢＣ中文_100%.pdf"), ("STRASSE", "Straße.pdf"), ("报告", "中文报告.pdf")]:
                body = request(a, "/documents", params={"name": term}).json()
                check("literal_unicode_filter_" + term, [(v["document_id"], v["display_name"]) for v in body["items"]] == [(fixture_ids[("A", expected)], expected)])
            same = request(a, "/documents", params={"name": "同名"}).json()["items"]
            check("same_names_private_and_notready_reason", len(same) == 1 and same[0]["document_id"] == fixture_ids[("A", "同名.pdf")]
                  and not same[0]["searchable"] and same[0]["job_status"] == "failed" and same[0]["error_code"] == "PAGE_ENCODING_FAILED")
            request(a, "/documents?name=a&name=b", 422)
            check("filename_listing_no_model_or_qdrant_query", not list((out / "query-audit").glob("*.json")) and not list((out / "filter-audit").glob("*.json")))
            first = request(a, "/documents", params={"limit": 2}).json()
            cursor, seen = first["next_cursor"], [i["document_id"] for i in first["items"]]
            first_cursor = cursor
            while cursor:
                page = request(a, "/documents", params={"limit": 2, "cursor": cursor}).json()
                seen.extend(i["document_id"] for i in page["items"])
                cursor = page["next_cursor"]
            check("pagination_complete_no_duplicates_or_cross_user", len(seen) == len(set(seen)) == 6 and new_b not in seen)
            request(b, "/documents", 422, params={"limit": 2, "cursor": first_cursor})
            request(a, "/documents", 422, params={"name": "changed", "limit": 2, "cursor": first_cursor})
            request(a, "/documents", 422, params={"limit": 3, "cursor": first_cursor})
            request(a, "/documents", 422, params={"limit": 2, "cursor": first_cursor + "!"})
            no_forward = len(list((out / "query-audit").glob("*.json")))
            for target, status in [(new_b, 404), (str(uuid4()), 404), (fixture_ids[("A", "同名.pdf")], 409), (fixture_ids[("A", "ＡＢＣ中文_100%.pdf")], 409), ("", 422), ("bad", 422)]:
                request(a, "/search", status, params={"q": "scope validation", "document_id": target})
            check("invalid_denied_notready_no_forward_no_library_fallback", len(list((out / "query-audit").glob("*.json"))) == no_forward)
            question = "What is the Aharonov-Bohm effect and how is the phase measured in the experiment?"
            library = query(a, "A_library", question)
            selected_old = query(a, "A_original", question, old_a)
            selected_new = query(a, "A_new", question, new_a)
            query(a, "A_new_repeat", question, new_a, k=3)
            query(b, "B_new", "What comparisons and conclusions are reported in the document?", new_b)
            check("library9_selected5_and4_distinct", len(library["items"]) == 9 and len(selected_old["items"]) == 5 and len(selected_new["items"]) == 4)
            check("higher_scoring_other_document_cannot_displace_selected_pages", max(i["page_score"] for i in library["items"] if i["document_id"] == new_a)
                  > max(i["page_score"] for i in library["items"] if i["document_id"] == old_a))
            hit = selected_new["items"][0]
            image = request(a, hit["preview_url"])
            check("selected_new_png_identity", sha(image.content) == hit["render_sha256"])
            request(b, hit["preview_url"], 404)
            # Clone-only sharing mutation; unchanged Qdrant payload never grants authority.
            with Session(engine) as db, db.begin():
                shared = db.get(Document, old_b)
                shared.owner_id, shared.visibility = users["admin"], "shared"
            request(a, "/documents", 409, params={"limit": 2, "cursor": first_cursor})
            shares = request(a, "/documents", params={"name": "music"}).json()["items"]
            check("active_admin_shared_ready_visible", len(shares) == 1 and shares[0]["document_id"] == old_b and shares[0]["access"] == "shared" and shares[0]["searchable"])
            shared_query = query(a, "A_shared", "What music generation methods are described?", old_b, k=3)
            shared_image = shared_query["items"][0]["preview_url"]
            request(a, shared_image)
            with Session(engine) as db, db.begin():
                db.get(Document, old_b).visibility = "private"
            request(a, "/search", 404, params={"q": "after revoke", "document_id": old_b})
            request(a, shared_image, 404)
            check("withdrawn_share_removed_from_list", request(a, "/documents", params={"name": "music"}).json()["items"] == [])
            with Session(engine) as db, db.begin():
                db.get(Document, old_b).visibility = "shared"
                db.get(User, users["admin"]).active = False
            check("disabled_admin_share_hidden", request(a, "/documents", params={"name": "music"}).json()["items"] == [])
            request(a, "/search", 404, params={"q": "disabled share", "document_id": old_b})
            current_cursor = request(a, "/documents", params={"limit": 2}).json()["next_cursor"]
            stop(); start(2)
            request(a, "/documents", params={"limit": 2, "cursor": current_cursor})
            request(a, hit["preview_url"])
            check("session_cursor_and_selected_png_survive_restart", True)
        audits = [json.loads(p.read_text(encoding="utf-8")) for p in (out / "query-audit").glob("*.json")]
        check("six_real_query_forwards_single_model_offline", len(audits) == 6 and len({v["worker_pid"] for v in audits}) == 1 and all(v["network_attempts"] == 0 for v in audits))
        check("no_page_reencoding", not list((out / "page-audit").glob("*.json")))
        check("all_reused_full_tensors_unchanged", len(feature_hashes) == 8 and all(sha((ROOT / p).read_bytes()) == value for p, value in feature_hashes.items()))
        check("entire_reused21_collection_unchanged", dynamic_fingerprint(active_collection, 21) == active_before)
        check("original13_collection_unchanged", vector_fingerprint(original["collection"]) == original["qdrant"])
        check("R15_source_database_read_only", snapshot(source_path) == source_before)
        (out / "reference-cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "passed", "checks": checks,
                  "real_query_forwards": len(audits), "page_forwards": 0, "worker_pid": audits[0]["worker_pid"], "network_attempts": 0,
                  "reused_collection": active_collection, "reused_page_count": 21, "reference_cases": str(out / "reference-cases.json"),
                  "limits": ["metadata fixture names/states are explicit fixtures, not new ingestion claims", "all original/full new tensors and collections reused read-only", "no UI, capacity or accuracy evaluation", "mid-inference revocation covered by unit tests; HTTP revokes between requests"]}
    except BaseException as exc:
        report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "failed", "error_type": type(exc).__name__, "checks": checks}
        raise
    finally:
        stop()
        if engine: engine.dispose()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R16 real selection: {len(checks)} checks passed;6 real queries,0 page encodings; isolated stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.attempt <= 99: parser.error("attempt must be1..99")
    main(args.attempt)
