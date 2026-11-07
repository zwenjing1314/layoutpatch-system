"""R15 formal additive schema and runtime verification, without formal credentials."""
import argparse
import importlib.metadata as metadata
import json
import subprocess

import httpx

from backend.db.connection import ROOT, DEFAULT_DATABASE, make_engine
from backend.main import app
from backend.search.scope import active_index
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/checks/stage2-2-formal-final.json")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "docs/checks") or output.exists():
        raise ValueError("output must be a new file under docs/checks")
    before = json.loads((ROOT / "docs/checks/stage2-2-preflight.json").read_text(encoding="utf-8"))
    current = snapshot(DEFAULT_DATABASE)
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    check("formal_0005_integrity_and_fk", current["revision"] == "0005_ingestion" and current["integrity"] == "ok" and current["foreign_key_errors"] == 0)
    check("all_existing_10_tables_logically_unchanged", all(current["tables"][t] == value for t,value in before["database"]["tables"].items() if t != "alembic_version"))
    check("only_active_pointer_and_feature_provenance_added", set(current["tables"]) - set(before["database"]["tables"]) == {"system_state", "page_features"})
    check("formal_feature_table_empty_and_no_test_uploads", current["tables"]["page_features"]["count"] == 0 and current["tables"]["jobs"]["count"] == 0)
    engine = make_engine(DEFAULT_DATABASE)
    with Session(engine) as db:
        index, _ = active_index(db)
        check("active_pointer_still_original13", index.collection_name == before["collection"] and index.page_count == 13)
    engine.dispose()
    migrate(DEFAULT_DATABASE)
    check("repeat_migration_no_changes", snapshot(DEFAULT_DATABASE) == current)
    check("original_qdrant_full_fingerprint_unchanged", vector_fingerprint(before["collection"]) == before["qdrant"])
    check("api_schema_unchanged_sdk_remains_current", app.openapi() == json.loads((ROOT / "frontend/docs/openapi.json").read_text(encoding="utf-8")))
    with httpx.Client(base_url="http://127.0.0.1:3000", trust_env=False, timeout=30) as client:
        check("production_frontend_200", client.get("/").status_code == 200)
        check("production_proxy_health_200", client.get("/api/health").status_code == 200)
        for path in ("/api/auth/me", "/api/search?q=r15-check", "/api/jobs/unknown", "/api/documents/unknown", "/api/pages/unknown/image"):
            response = client.get(path)
            check("protected_anonymous_401_" + path.split("?")[0], response.status_code == 401 and response.headers.get("cache-control") == "private, no-store")
        response = client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")}, headers={"Origin": "https://attacker.invalid"})
        check("upload_origin_protection_403", response.status_code == 403)
        response = client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7", "application/pdf")}, headers={"Origin": "http://127.0.0.1:3000"})
        check("upload_anonymous_401", response.status_code == 401)
    check("anonymous_checks_do_not_change_formal_rows", snapshot(DEFAULT_DATABASE) == current)
    previous_web = json.loads((ROOT / "docs/checks/stage2-1-preflight.json").read_text(encoding="utf-8"))["web_packages"]
    expected_packages = sorted(previous_web + [["python-multipart", "0.0.20"]])
    check("web_dependencies_unchanged_since_2_1", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == expected_packages)
    listeners = json.loads(subprocess.check_output([
        "powershell", "-NoProfile", "-Command",
        "Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"
    ], text=True))
    ports = {row["LocalPort"]: row["OwningProcess"] for row in listeners}
    check("required_services_listening_and_isolated_port_stopped", all(p in ports for p in (3000,8000,6333)) and 8001 not in ports)
    report = {"date": "2026-11-07", "round": "R15", "stage": "2-2", "status": "passed", "checks": checks,
              "database": current, "formal_credentials_used": False,
              "runtime": {"frontend_port": 3000, "frontend_pid": ports[3000], "backend_port": 8000, "backend_pid": ports[8000],
                          "qdrant_port": 6333, "qdrant_pid": ports[6333], "isolated_8001": "stopped"},
              "limitations": ["production DB remains original13; real new upload evidence isolated", "anonymous production checks only; no formal credentials"]}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R15 formal: {len(checks)} checks passed; original data and vectors unchanged")


if __name__ == "__main__":
    main()
