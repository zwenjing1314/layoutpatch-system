"""Finalize R19 evidence and verify scope/history without changing application data."""
import ast
from datetime import datetime
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil
import subprocess

from backend.db.connection import DEFAULT_DATABASE, ROOT
from scripts.check_stage2_preflight import snapshot
from scripts.check_task_recovery import OUT, UI, read, write

CHECKS = ROOT / "docs/checks"
DOCS = {"docs/" + name for name in (
    "AI交接.md", "progress.md", "testing.md", "requirements.md", "architecture.md", "interfaces.md",
    "项目开发阶段规划与任务.md", "阶段2新窗口接手指南.md", "前端工作台改版方案与复用评估.md",
    "单文档检索功能设计与分批计划.md", "stage2-3c-runbook.md", "过程记录/07_2技术操作详解.md", "过程记录/08_2逐步口述稿.md")}
CODE = set("""backend/db/models.py backend/db/seed.py backend/documents/ingest.py backend/documents/pipeline.py backend/documents/task_state.py backend/documents/tasks.py backend/main.py
migrations/versions/0007_job_attempts.py tests/test_auth.py tests/test_tasks.py
frontend/app/page.tsx frontend/app/workspace.css frontend/components/workspace/workspace.tsx frontend/components/workspace/upload-tasks.tsx
frontend/lib/task-state.ts frontend/lib/use-upload-tasks.ts frontend/docs/openapi.json frontend/lib/api/generated/index.ts frontend/lib/api/generated/models/JobResponse.ts
frontend/lib/api/generated/models/JobActionInput.ts frontend/lib/api/generated/models/JobAttemptResponse.ts frontend/lib/api/generated/models/JobListResponse.ts frontend/lib/api/generated/services/DocumentsService.ts
frontend/tests/load-workspace.cjs frontend/tests/workspace-components.test.cjs frontend/tests/upload-tasks.test.cjs
scripts/check_task_recovery.py scripts/task_recovery_server.py scripts/check_task_recovery_evidence.py scripts/check_task_feature_cache.py scripts/check_task_recovery_documents.py""".split())
REPORTS = set("""stage2-3c-preflight.json stage2-3c-http.json stage2-3c-runtime.json stage2-3c-formal.json stage2-3c-formal-attempt1.json
stage2-3c-features.json stage2-3c-migration.json stage2-3c-browser.json stage2-3c-failures.json r19-document-checks.json stage2-3c-verification.json
source-state-r19-before.json source-state-r19-final.json""".split())
SHOTS = {"tasks-final-laptop.jpg": "stage2-3c-laptop.jpg", "tasks-small320.jpg": "stage2-3c-small320.jpg",
         "tasks-long390.jpg": "stage2-3c-long390.jpg", "A-single.jpg": "stage2-3c-A-single.jpg", "B-single.jpg": "stage2-3c-B-single.jpg",
         "cancel-pending.jpg": "stage2-3c-cancel-pending.jpg", "B-interrupted.jpg": "stage2-3c-interrupted.jpg"}
ARTIFACTS = {"docs/checks/" + name for name in REPORTS | set(SHOTS.values())}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary_path, doc_path = CHECKS / "stage2-3c-verification.json", CHECKS / "r19-document-checks.json"
    if any((CHECKS / name).exists() for name in ("stage2-3c-browser.json", "stage2-3c-failures.json", "stage2-3c-verification.json", "r19-document-checks.json")):
        raise RuntimeError("Final R19 evidence exists; preserve before rerunning")
    baseline = read(CHECKS / "stage2-3c-preflight.json")
    formal, http, runtime = [read(CHECKS / ("stage2-3c-" + name + ".json")) for name in ("formal", "http", "runtime")]
    browser = read(UI / "browser-checks.json")
    write(CHECKS / "stage2-3c-browser.json", {"date": datetime.now().astimezone().isoformat(), "round": "R19", "overall": "passed", "checks": [{"number": i, "name": item["id"], "passed": item["pass"], **({"detail": item["detail"]} if "detail" in item else {})} for i, item in enumerate(browser, 1)], "raw": "runtime/verification/r19/ui/browser-checks.json", "build": "runtime/verification/r19/build.log", "limits": runtime["limits"] + ["36 checks use one final build; responsive snapshots are sampled geometries, not full accessibility certification", "First-password-change gate observed without entering/submitting new credentials", "Disconnect first clears task cards, then scheduled auth check locks workspace; reconnect used", "10-minute browser polling wall-clock pause not manually waited; source/contract and bounded-request tests cover behavior"]})
    write(CHECKS / "stage2-3c-failures.json", {"date": datetime.now().astimezone().isoformat(), "round": "R19", "unresolved": [], "records": [
        {"issue": "Seed accepted revision list omitted0007", "evidence": "runtime/verification/r19/backend-attempt1.log", "resolution": "Added legitimate head revision; final87 passed"},
        {"issue": "Concurrent test nested TestClient lifespans closed shared engine; Windows temporary SQLite cleanup locked", "evidence": "runtime/verification/r19/backend-attempt1.log", "resolution": "Use one started client for concurrent actions; preserves real SQLite race coverage"},
        {"issue": "Exact route allow-list omitted3 task endpoints", "evidence": "runtime/verification/r19/backend-final.log", "resolution": "Explicitly register /jobs,retry,cancel; final87 in38.671s passed"},
        {"issue": "Prepare2-4-page selection found fewer than2 distinct new PDFs", "evidence": "runtime/verification/r19/ui-prepare-attempt1", "resolution": "Preserved entire failed directory; choose sorted filenames with2-6 pages, actually5/6; failed before GPU"},
        {"issue": "Formal anonymous upload probe used JSON and got415 before expected401", "evidence": "docs/checks/stage2-3c-formal-attempt1.json", "resolution": "Use legal multipart media, then verify anonymous401; keep Origin403. No application protection changed;29 final passed"},
        {"issue": "Scheduled auth check locked UI before planned task-refresh click after hard restart", "resolution": "Observed unavailable state and used reconnect; recorded actual path, not claimed direct refresh"},
        {"issue": "Read-only audit_sources candidate did not exist; one Python stdout used GBK and could not print frontend checkmark", "resolution": "Use actual snapshot_sources and explicit PYTHONUTF8=1; no application/file corruption"},
        {"issue": "Existing baseline-browser-mapping stale-data warning and Git LF/CRLF notices", "resolution": "Build/diff checks passed; no dependency/ignore upgrade"},
    ]})
    for source, target in SHOTS.items():
        destination = CHECKS / target
        if destination.exists():
            raise RuntimeError("Screenshot destination exists; refusing overwrite")
        shutil.copyfile(UI / source, destination)
    # Create self-link targets before checking documentation links.
    write(summary_path, {"round": "R19", "overall": "building"})
    write(doc_path, {"round": "R19", "overall": "building"})
    checks = []
    def check(name, condition, **detail):
        checks.append({"name": name, "passed": bool(condition), **detail})
        if not condition:
            write(doc_path, {"round": "R19", "overall": "failed", "checks": checks})
            raise AssertionError(name)
    for name, report, count in (("HTTP", http, 39), ("runtime", runtime, 30), ("formal", formal, 29)):
        check(name + "_all_expected_checks_passed", report["overall"] == "passed" and len(report["checks"]) == count and all(r["passed"] for r in report["checks"]))
    check("36_browser_checks_passed", len(browser) == 36 and all(r["pass"] for r in browser))
    check("formal_DB_still_equals_restored0007_snapshot", snapshot(DEFAULT_DATABASE) == formal["database"])
    check("old_project_git_selected_files_model_dependencies_unchanged", read(CHECKS / "source-state-r19-before.json") == read(CHECKS / "source-state-r19-final.json"))
    check("web_packages_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == baseline["web_packages"])
    changed = [name for name, sha in baseline["files"].items() if not (ROOT / name).is_file() or digest(ROOT / name) != sha]
    check("only_intended_preexisting_files_changed", set(changed) <= DOCS | CODE, changed=changed)
    history = [name for name in baseline["files"] if name.startswith("docs/过程记录/0") and not name.startswith(("docs/过程记录/07_", "docs/过程记录/08_"))]
    check("01_06_original_bytes_preserved", len(history) == 6 and all(digest(ROOT / name) == baseline["files"][name] for name in history))
    check("old_check_reports_preserved", all(digest(ROOT / name) == sha for name, sha in baseline["files"].items() if name.startswith("docs/checks/")))
    protected = [name for name in baseline["files"] if name.startswith(("backend/algorithms/", "configs/", "requirements-")) or name in {".gitignore", "AGENTS.md", "frontend/package.json", "frontend/yarn.lock", "frontend/app/globals.css", "frontend/lib/workspace-lifecycle.ts", "backend/auth/boundary.py", "backend/auth/routes.py", "frontend/app/api/[...path]/route.ts"}]
    check("algorithm_model_locks_origin_auth_proxy_login_CSS_unchanged", all(digest(ROOT / name) == baseline["files"][name] for name in protected), files=len(protected))
    learned = []
    for name in ("07_2技术操作详解.md", "08_2逐步口述稿.md"):
        path = ROOT / "docs/过程记录" / name
        data = path.read_bytes()
        marker = "\n\n## 2026-11-08｜R19｜".encode()
        check("all_prior_learning_bytes_preserved_" + name[:2], hashlib.sha256(data.split(marker)[0]).hexdigest() == baseline["files"][path.relative_to(ROOT).as_posix()])
        parts = re.findall(r"^## (2026-11-08｜R19｜2-3C｜S\d+：[^\n]+)\n\n(.*?)(?=\n## |\Z)", path.read_text(encoding="utf-8"), re.M | re.S)
        check("six_R19_learning_steps_" + name[:2], len(parts) == 6)
        learned.append(parts)
    check("paired_date_round_stage_step_titles", [h for h, _ in learned[0]] == [h for h, _ in learned[1]])
    lengths = [len(text.strip()) for _, text in learned[1]]
    check("oral60_to100_characters", all(60 <= length <= 100 for length in lengths), lengths=lengths)
    links, missing = 0, []
    for name in sorted(DOCS):
        for value in re.findall(r"\[[^\]]*\]\(([^)]+)\)", (ROOT / name).read_text(encoding="utf-8")):
            value = value.split("#", 1)[0]
            if not value or re.match(r"^[a-zA-Z]+://", value):
                continue
            links += 1
            if not ((ROOT / name).parent / value).exists():
                missing.append({"document": name, "target": value})
    check("document_local_links_resolve", not missing, checked=links, missing=missing)
    for name in CODE:
        if name.endswith(".py"):
            ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    for name in REPORTS:
        read(CHECKS / name)
    check("scripts_and_reports_parse", True)
    check("feature_and_legacy_migration_evidence_passed", read(CHECKS / "stage2-3c-features.json")["overall"] == read(CHECKS / "stage2-3c-migration.json")["overall"] == "passed")
    check("seven_screenshot_copies_match", all(digest(CHECKS / target) == digest(UI / source) for source, target in SHOTS.items()))
    paths = {p.relative_to(ROOT).as_posix(): p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "frontend/components", "frontend/tests", "configs", "docs") for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts}
    paths.update({"docs/checks/" + name: CHECKS / name for name in SHOTS.values()})
    delta = {name: path for name, path in paths.items() if name not in baseline["files"] or digest(path) != baseline["files"][name]}
    check("complete_scanned_delta_within_scope", set(delta) <= DOCS | CODE | ARTIFACTS, unexpected=sorted(set(delta) - DOCS - CODE - ARTIFACTS))
    check("all_expected_code_docs_evidence_present", all((ROOT / name).is_file() for name in DOCS | CODE | ARTIFACTS))
    private = read(UI / "state.json")
    check("no_test_passwords_in_deliverables", all(secret not in path.read_text(encoding="utf-8-sig") for secret in private["passwords"].values() for path in delta.values() if path.suffix != ".jpg"))
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True)
    check("git_diff_check_passed", diff.returncode == 0)
    check("git_index_empty", not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip())
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").rstrip("\0")
    check("new_unignored_files_expected", set(untracked.split("\0") if untracked else []) <= CODE)
    new_docs = sorted(name for name in DOCS | ARTIFACTS if name not in baseline["files"])
    ignore = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], cwd=ROOT, input="\0".join(new_docs) + "\0", capture_output=True, text=True, encoding="utf-8")
    check("new_local_docs_follow_original_ignore", ignore.returncode == 0 and set(ignore.stdout.rstrip("\0").split("\0")) == set(new_docs), count=len(new_docs))
    backend = (OUT / "backend-final2.log").read_text(encoding="utf-8-sig")
    front = (OUT / "frontend-attempt1.log").read_text(encoding="utf-8-sig")
    algo = (OUT / "algorithm-contracts.log").read_text(encoding="utf-8-sig")
    build = (OUT / "build.log").read_text(encoding="utf-8-sig")
    check("final_test_logs_match_counts_and_times", "Ran 87 tests in 38.671s" in backend and backend.rstrip().endswith("OK") and "pass 25" in front and "fail 0" in front and "377.422" in front and "4 passed in 2.35s" in algo)
    check("final_build_and_typecheck_logs_present", "Compiled successfully" in build and "Finalizing page optimization" in build and (OUT / "typecheck.log").stat().st_size == 0)
    ps = lambda command: subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True).strip()
    ports = json.loads(ps("@(Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess) | ConvertTo-Json -Compress"))
    check("formal_ports_still_restored_8001_free", {p["LocalPort"] for p in ports} == {3000, 8000, 6333}, ports=ports)
    workers = ps("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scripts/model_query_worker.py*' } | Select-Object ProcessId) | ConvertTo-Json -Compress")
    check("no_test_model_tree_remaining", not workers or json.loads(workers) == [])
    check("runtime_16_pages_4_queries_two_workers_network0", runtime["actual_page_forwards"] == 16 and runtime["actual_query_forwards"] == 4 and runtime["worker_pids"] == [36316, 40440] and runtime["network_attempts"] == 0)
    write(doc_path, {"date": datetime.now().astimezone().isoformat(), "round": "R19", "overall": "passed", "checks": checks, "limits": "Scope audit compares baseline-selected source/docs/model dependencies; no ignored full-disk audit. Tests are actual earlier R19 runs, not rerun by this document pass."})
    modified = [{"path": name, "change": "modified" if name in baseline["files"] else "new", "sha256": None if path == summary_path else digest(path)} for name, path in sorted(delta.items())]
    write(summary_path, {"date": datetime.now().astimezone().isoformat(), "round": "R19", "stage": "2-3C", "overall": "passed", "scope": "Protected upload/task UI, owner task discovery and attempt-bound retry/cancel; no MinerU/D/highlight/history/budget implementation", "tests": {"backend": {"passed": 87, "seconds": 38.671}, "frontend": {"passed": 25, "milliseconds": 377.422}, "algorithm_CPU": {"passed": 4, "seconds": 2.35}, "TypeScript": "passed", "production_build": "passed", "HTTP": 39, "browser": 36, "runtime": 30, "formal": 29, "legacy_migration": "passed", "full_feature_tensors": 16, "document_protection": len(checks)}, "actual_page_forwards": 16, "cancelled_attempt_page_forwards": 5, "activated_new_full_features": 11, "actual_query_forwards": 4, "sequential_model_worker_pids": [40440, 36316], "network_attempts": 0, "formal_database": {"revision": "0007_job_attempts", "original_pages": 13, "documents": 2, "jobs_attempts_features": 0}, "ports": ports, "formal_credentials_read_used_changed": False, "git_stage_commit_push_executed": False, "modified_files": modified, "self_report_hash": "omitted to avoid recursion; all other manifest hashes verified after write", "private_runtime": "runtime/verification/r19 retained locally; random test credentials and detailed runtime logs excluded from public file manifest", "unresolved_blockers": [], "next_unique_task": "2-4: real MinerU parsing and coordinate contract; wait for user", "limits": read(CHECKS / "stage2-3c-browser.json")["limits"]})
    assert all(row["sha256"] is None or digest(ROOT / row["path"]) == row["sha256"] for row in read(summary_path)["modified_files"])
    print(f"R19 complete: {len(checks)} document/protection checks;{len(modified)} changed/new files; oral lengths{lengths};manifest hashes verified; no staged files or credentials printed")


if __name__ == "__main__":
    main()
