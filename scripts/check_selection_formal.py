"""R16 formal additive column, old data preservation and anonymous production proxy checks."""
from contextlib import closing
import importlib.metadata as metadata
import json
import sqlite3
import subprocess
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from backend.db.connection import ROOT, DEFAULT_DATABASE, make_engine
from backend.db.seed import sha
from backend.documents.names import normalize_name
from backend.main import app
from backend.search.scope import active_index
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate


def main():
    destination = ROOT / "docs/checks/stage2-3a-formal.json"
    if destination.exists():
        raise RuntimeError("Formal report exists; choose a new evidence path")
    before = json.loads((ROOT / "docs/checks/stage2-3a-preflight.json").read_text(encoding="utf-8"))
    current = snapshot(DEFAULT_DATABASE)
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition: raise AssertionError(name)
    check("formal_0006_integrity_ok_fk0", current["revision"] == "0006_document_names" and current["integrity"] == "ok" and current["foreign_key_errors"] == 0)
    check("same_tables_no_rebuild_or_new_table", set(before["database"]["tables"]) == set(current["tables"]))
    check("all_11_non_document_business_auth_tables_unchanged", all(current["tables"][t] == value for t, value in before["database"]["tables"].items() if t not in {"documents", "alembic_version"}))
    with closing(sqlite3.connect(ROOT / "runtime/verification/r16/metadata-before.sqlite3")) as old, closing(sqlite3.connect(DEFAULT_DATABASE)) as db:
        old_columns = [r[1] for r in old.execute("PRAGMA table_info(documents)")]
        new_columns = [r[1] for r in db.execute("PRAGMA table_info(documents)")]
        check("only_normalized_name_column_added", new_columns == old_columns + ["display_name_key"])
        projection = ",".join('"'+c+'"' for c in old_columns)
        check("all_old_document_columns_unchanged", sorted(old.execute("SELECT " + projection + " FROM documents").fetchall()) == sorted(db.execute("SELECT " + projection + " FROM documents").fetchall()))
        check("normalized_keys_backfilled_without_renaming", all(key == normalize_name(name) for name, key in db.execute("SELECT display_name, display_name_key FROM documents")))
        check("normalized_key_index_exists", "ix_documents_display_name_key" in {r[1] for r in db.execute("PRAGMA index_list(documents)")})
    engine = make_engine(DEFAULT_DATABASE)
    with Session(engine) as db:
        index, _ = active_index(db)
        check("original13_active_pointer_unchanged", index.collection_name == before["collection"] and index.page_count == 13)
    engine.dispose()
    check("no_formal_test_documents_jobs_or_features", current["tables"]["documents"]["count"] == 2 and current["tables"]["jobs"]["count"] == current["tables"]["page_features"]["count"] == 0)
    migrate(DEFAULT_DATABASE)
    check("repeat_migration_no_changes", snapshot(DEFAULT_DATABASE) == current)
    check("original_full_qdrant_fingerprint_unchanged", vector_fingerprint(before["collection"]) == before["qdrant"])
    check("exported_OpenAPI_current", app.openapi() == json.loads((ROOT / "frontend/docs/openapi.json").read_text(encoding="utf-8")))
    check("generated_SDK_includes_both_new_inputs", "listDocuments(" in (ROOT / "frontend/lib/api/generated/services/DocumentsService.ts").read_text()
          and "'document_id': documentId" in (ROOT / "frontend/lib/api/generated/services/SearchService.ts").read_text())
    with httpx.Client(base_url="http://127.0.0.1:3000", timeout=30, trust_env=False) as client:
        check("production_home_and_health_200", client.get("/").status_code == client.get("/api/health").status_code == 200)
        for path in ("/api/documents", "/api/documents?name=private&limit=1", "/api/search?q=scope-check&document_id=" + str(uuid4()),
                     "/api/auth/me", "/api/search?q=legacy-check", "/api/jobs/unknown", "/api/documents/unknown", "/api/pages/unknown/image"):
            response = client.get(path)
            check("anonymous_401_" + path.split("?")[0], response.status_code == 401 and response.headers.get("cache-control") == "private, no-store" and "cookie" in {value.strip().lower() for value in response.headers.get("vary", "").split(",")})
        check("upload_origin_still403", client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")}, headers={"Origin": "https://attacker.invalid"}).status_code == 403)
        check("upload_same_origin_anonymous401", client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")}, headers={"Origin": "http://127.0.0.1:3000"}).status_code == 401)
    check("anonymous_checks_leave_formal_data_unchanged", snapshot(DEFAULT_DATABASE) == current)
    check("Web_dependencies_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == before["web_packages"])
    listeners = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command",
        "Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"], text=True))
    ports = {row["LocalPort"]: row["OwningProcess"] for row in listeners}
    check("production_listening_and_isolated_stopped", all(port in ports for port in (3000,8000,6333)) and 8001 not in ports)
    report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "passed", "checks": checks, "database": current,
              "runtime": {"frontend_port": 3000, "frontend_pid": ports[3000], "backend_port": 8000, "backend_pid": ports[8000], "qdrant_port": 6333, "qdrant_pid": ports[6333], "isolated8001": "stopped"},
              "formal_credentials_used": False, "limits": ["formal HTTP anonymous only; authenticated feature/GPU checks use isolated clone", "display_name_key additive backfill is the only business metadata change"]}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R16 formal: {len(checks)} checks passed; original columns/vectors preserved,normalized keys added")


if __name__ == "__main__":
    main()
