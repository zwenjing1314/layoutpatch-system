"""Verify formal additive migration and anonymous production proxy, without formal credentials."""
from contextlib import closing
import importlib.metadata as metadata
import json
import sqlite3

import httpx

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint
from scripts.migrate_database import migrate


def main():
    results = []

    def check(name, condition):
        results.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    before = json.loads((ROOT / "docs/checks/stage2-1-preflight.json").read_text(encoding="utf-8"))
    after = snapshot(DEFAULT_DATABASE)
    check("formal_revision_0004_integrity_fk", after["revision"] == "0004_upload_jobs" and after["integrity"] == "ok" and after["foreign_key_errors"] == 0)
    check("all_existing_9_tables_logically_unchanged", all(after["tables"][t] == value for t, value in before["database"]["tables"].items() if t != "alembic_version"))
    check("only_jobs_added_empty", set(after["tables"]) - set(before["database"]["tables"]) == {"jobs"} and after["tables"]["jobs"]["count"] == 0)
    migrate(DEFAULT_DATABASE)
    check("migration_repeat_no_changes", snapshot(DEFAULT_DATABASE) == after)
    with httpx.Client(base_url="http://127.0.0.1:3000", trust_env=False, timeout=30) as client:
        check("production_home_200", client.get("/").status_code == 200)
        check("production_health_200", client.get("/api/health").status_code == 200)
        for path in ("/api/auth/me", "/api/search?q=stage2-test", "/api/jobs/unknown", "/api/documents/unknown", "/api/pages/unknown/image"):
            response = client.get(path)
            check("anonymous_401_" + path.split("?")[0], response.status_code == 401 and response.headers.get("cache-control") == "private, no-store")
        response = client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")}, headers={"Origin": "https://attacker.invalid"})
        check("proxy_origin_403", response.status_code == 403)
        response = client.post("/api/index", files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")}, headers={"Origin": "http://127.0.0.1:3000"})
        check("proxy_upload_anonymous_401", response.status_code == 401 and response.headers.get("cache-control") == "private, no-store")
        response = client.post("/api/index", files={"file": ("large.pdf", b"x" * (20 * 1024 * 1024), "application/pdf")}, headers={"Origin": "http://127.0.0.1:3000"})
        check("proxy_accepts_20mib_body_to_auth_boundary_401", response.status_code == 401)
        check("no_bare_files_route", client.get("/api/files/uploads/source.pdf").status_code == 404)
    check("anonymous_checks_do_not_change_formal_rows", snapshot(DEFAULT_DATABASE) == after)
    prior_packages = {name.lower().replace("_", "-"): version for name, version in before["web_packages"]}
    packages = {d.metadata["Name"].lower().replace("_", "-"): d.version for d in metadata.distributions()}
    check("web_only_adds_python_multipart", set(packages) - set(prior_packages) == {"python-multipart"}
          and all(packages[name] == version for name, version in prior_packages.items()) and packages["python-multipart"] == "0.0.20")
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as db:
        collection = db.execute("SELECT collection_name FROM index_generations WHERE status='ready'").fetchone()[0]
    reference = json.loads((ROOT / "docs/checks/stage2-1-http-attempt2.json").read_text(encoding="utf-8"))["qdrant"]
    check("formal_qdrant_full_fingerprint_unchanged", vector_fingerprint(collection) == reference)
    report = {"date": "2026-11-07", "round": "R14", "stage": "2-1", "status": "passed", "checks": results,
              "database": after, "formal_credentials_used": False,
              "limitations": ["proxy upload authenticated success tested via direct isolated HTTP, no upload UI in 2-1", "no new GPU query or algorithm run"]}
    (ROOT / "docs/checks/stage2-1-formal.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Formal migration/proxy: {len(results)} checks passed; existing data unchanged")


if __name__ == "__main__":
    main()
