"""Finalize R18 local evidence without changing application, data, or services."""
from collections import Counter
from datetime import datetime
import ast
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil
import subprocess

from backend.db.connection import DEFAULT_DATABASE, ROOT
from scripts.check_stage2_preflight import snapshot

OUT = ROOT / "runtime/verification/r18"
CHECKS = ROOT / "docs/checks"
DOCS = {
    "docs/AI交接.md", "docs/progress.md", "docs/testing.md", "docs/requirements.md",
    "docs/architecture.md", "docs/interfaces.md", "docs/项目开发阶段规划与任务.md",
    "docs/阶段2新窗口接手指南.md", "docs/前端工作台改版方案与复用评估.md",
    "docs/单文档检索功能设计与分批计划.md", "docs/stage2-3b2-runbook.md",
    "docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md",
}
CODE = {
    "frontend/app/page.tsx", "frontend/app/workspace.css",
    "frontend/components/workspace/workspace.tsx",
    "frontend/components/workspace/document-picker.tsx", "frontend/lib/document-selection.ts",
    "frontend/tests/workspace-components.test.cjs", "frontend/tests/document-selection.test.cjs",
    "frontend/tests/load-workspace.cjs", "scripts/check_workspace_selection.py",
    "scripts/workspace_selection_server.py", "scripts/check_workspace_selection_documents.py",
}
SCREENSHOTS = {
    "final-single-laptop.jpg": "stage2-3b2-laptop.jpg",
    "final-library-laptop.jpg": "stage2-3b2-library.jpg",
    "final2-picker-small320.jpg": "stage2-3b2-small320.jpg",
    "final2-preview-mobile390.jpg": "stage2-3b2-mobile390.jpg",
    "final2-single-wide1920.jpg": "stage2-3b2-wide1920.jpg",
    "final-list-disconnected.jpg": "stage2-3b2-list-disconnected.jpg",
}
REPORT_NAMES = {
    "stage2-3b2-preflight.json", "stage2-3b2-http.json", "stage2-3b2-formal.json",
    "stage2-3b2-browser.json", "stage2-3b2-failures.json", "r18-document-checks.json",
    "stage2-3b2-verification.json", "source-state-r18-before.json", "source-state-r18-final.json",
}
ARTIFACTS = {"docs/checks/" + name for name in REPORT_NAMES | set(SCREENSHOTS.values())}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ps_json(command):
    raw = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True).strip()
    if not raw:
        return []
    value = json.loads(raw)
    return value if isinstance(value, list) else [value]


def main():
    report_path = CHECKS / "stage2-3b2-verification.json"
    doc_path = CHECKS / "r18-document-checks.json"
    generated = (report_path, doc_path, CHECKS / "stage2-3b2-browser.json", CHECKS / "stage2-3b2-failures.json")
    if any(path.exists() for path in generated):
        raise RuntimeError("R18 final evidence already exists; preserve it and inspect before another run")
    baseline = read(CHECKS / "stage2-3b2-preflight.json")
    formal = read(CHECKS / "stage2-3b2-formal.json")
    http = read(CHECKS / "stage2-3b2-http.json")
    browser = read(OUT / "ui/browser-checks.json")
    events = [json.loads(line) for line in (OUT / "ui/http-observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    phases = [
        {"name": "initial", "checks_first": 1, "checks_last": 28, "count": 28, "build_log": "runtime/verification/r18/build.log"},
        {"name": "picker_focus_fix", "checks_first": 29, "checks_last": 44, "count": 16, "build_log": "runtime/verification/r18/build-focus.log"},
        {"name": "final_notice_fix", "checks_first": 45, "checks_last": 65, "count": 21, "build_log": "runtime/verification/r18/build-final2.log"},
    ]
    write(CHECKS / "stage2-3b2-browser.json", {
        "date": datetime.now().astimezone().isoformat(), "round": "R18", "overall": "passed",
        "raw_evidence": "runtime/verification/r18/ui/browser-checks.json",
        "phases": phases,
        "checks": [{"number": i, "build_phase": next(p["name"] for p in phases if p["checks_first"] <= i <= p["checks_last"]), **item} for i, item in enumerate(browser, 1)],
        "http_search_status_counts": dict(Counter(str(e["status"]) for e in events if e["path"] == "/search")),
        "authorized_png_responses": sum(e["path"].startswith("/pages/") and e["status"] == 200 for e in events),
        "data": "isolated R15 completed21 clone; duplicate names, shared4 and12 unready metadata are explicit fixtures",
        "faults": "3s list/5s search delays; isolated adapter connection refusal; no container stop",
        "limits": [
            "65 checks span three builds; final build has21 added checks, not65 reruns",
            "10 model forwards include a cancelled response and a dependency failure",
            "session revocation observed on auth/me401 before planned search; anonymous HTTP/search401 separately observed",
            "disconnect reached unavailable after list failure; recovery used reconnect",
            "first-password-change gate only, no submitted password change",
            "no new full BFCache/cross-tab/corrupt-or-interrupted-PNG/capacity/accessibility audit",
            "no new official scoring run; prior R16 scores are historical only",
        ],
    })
    write(CHECKS / "stage2-3b2-failures.json", {"date": datetime.now().astimezone().isoformat(), "round": "R18", "unresolved": [], "records": [
        {"issue": "First SSR assertion depended on HTML attribute order", "evidence": "runtime/verification/r18/frontend-tests-attempt1.log", "resolution": "Match attributes independently; final18 tests passed"},
        {"issue": "Isolated prepare passed nonexistent Job.document_id", "evidence": "runtime/verification/r18/ui-prepare-attempt1", "resolution": "Use document_version_id and required legal fields; failed transaction rolled back, failed clone preserved; formal database untouched"},
        {"issue": "Read-only probes used wrong cwd or nonexisting candidate filenames", "detail": "backend path from frontend, api-sdk.test.cjs and check_workspace_shell_documents.py candidates", "resolution": "Read actual listed paths; no application mutation"},
        {"issue": "CUA waited for empty fieldset visibility", "resolution": "Observe real no-match message instead; no-match state correct"},
        {"issue": "Radio check reported no-match after selection collapsed list", "resolution": "Inspect selected scope and focus, then use click plus post-state checks"},
        {"issue": "PNG-visible wait ran in narrow results view; change-document lookup ran in retained preview view", "resolution": "Observe actual current view and select appropriate results/preview tab before checking"},
        {"issue": "Scheduled auth/me401 preceded planned browser/search401; disconnect recheck preceded planned list refresh", "resolution": "Record actual gate and reconnect path; do not claim unexecuted paths"},
        {"issue": "Reopening picker retained old results scroll position", "resolution": "Scroll picker to top and focus filename; final320/390/1920 browser checks passed"},
        {"issue": "Successful list refresh retained stale notice", "resolution": "Clear matching old list warning; rebuild and add21 final-build browser checks"},
        {"issue": "Earlier multi-document patch had wrong architecture heading", "resolution": "Atomic patch refused with no writes; one-shot guarded sync completed documented files"},
        {"issue": "Runbook replacement requested delete and add for same path", "resolution": "Atomic patch refused with no writes; corrected to a single Update operation"},
        {"issue": "Existing baseline-browser-mapping age warning", "resolution": "Production build passed; no dependency upgrade"},
    ]})
    for source, target in SCREENSHOTS.items():
        destination = CHECKS / target
        if destination.exists():
            if digest(destination) != digest(OUT / "ui" / source):
                raise RuntimeError("Different screenshot exists; refusing overwrite")
        else:
            shutil.copyfile(OUT / "ui" / source, destination)

    # Establish self-link targets before checking updated documentation links.
    write(report_path, {"overall": "building", "round": "R18"})
    write(doc_path, {"overall": "building", "round": "R18"})
    checks = []

    def check(name, condition, **detail):
        checks.append({"name": name, "passed": bool(condition), **detail})
        if not condition:
            write(doc_path, {"date": datetime.now().astimezone().isoformat(), "round": "R18", "overall": "failed", "checks": checks})
            raise AssertionError(name)

    check("all65_browser_checks_passed_across_three_builds", len(browser) == 65 and all(item["passed"] for item in browser))
    check("all16_HTTP_checks_passed", http["overall"] == "passed" and len(http["checks"]) == 16 and all(item["passed"] for item in http["checks"]))
    check("all21_formal_checks_passed", formal["overall"] == "passed" and len(formal["checks"]) == 21 and all(item["passed"] for item in formal["checks"]))
    check("database_still_equals_opening_snapshot", snapshot(DEFAULT_DATABASE) == baseline["database"])
    check("old_project_git_selected_files_and_model_environment_unchanged", read(CHECKS / "source-state-r18-before.json") == read(CHECKS / "source-state-r18-final.json"))
    check("web_packages_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == baseline["web_packages"])
    changed = [name for name, sha in baseline["files"].items() if not (ROOT / name).is_file() or digest(ROOT / name) != sha]
    check("only_intended_preexisting_files_changed", set(changed) <= DOCS | CODE, changed=changed)
    histories = [name for name in baseline["files"] if name.startswith("docs/过程记录/0") and not name.startswith(("docs/过程记录/07_", "docs/过程记录/08_"))]
    check("history01_06_original_bytes_preserved", len(histories) == 6 and all(digest(ROOT / name) == baseline["files"][name] for name in histories), count=len(histories))
    check("all_preexisting_check_reports_unchanged", all(digest(ROOT / name) == sha for name, sha in baseline["files"].items() if name.startswith("docs/checks/")))
    protected = [name for name in baseline["files"] if name.startswith(("backend/", "migrations/", "configs/", "frontend/lib/api/", "requirements-")) or name in (".gitignore", "AGENTS.md", "frontend/package.json", "frontend/yarn.lock", "frontend/app/globals.css", "frontend/lib/workspace-lifecycle.ts")]
    check("backend_SDK_schema_model_locks_auth_CSS_and_lifecycle_unchanged", all(digest(ROOT / name) == baseline["files"][name] for name in protected), files=len(protected))

    learning = []
    for name in ("docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md"):
        data = (ROOT / name).read_bytes()
        prefix = data.split("## 2026-11-08｜R18｜".encode())[0].rstrip(b"\r\n")
        candidates = [prefix + ending for ending in (b"", b"\n", b"\r\n", b"\n\n", b"\r\n\r\n")]
        check("prior_learning_bytes_preserved_" + Path(name).name[:2], any(hashlib.sha256(candidate).hexdigest() == baseline["files"][name] for candidate in candidates))
        parts = re.findall(r"^## (2026-11-08｜R18｜2-3B-2｜S\d+：[^\n]+)\n\n(.*?)(?=\n## |\Z)", (ROOT / name).read_text(encoding="utf-8"), re.M | re.S)
        check("five_R18_steps_" + Path(name).name[:2], len(parts) == 5)
        learning.append(parts)
    check("learning_date_round_and_steps_pair", [h for h, _ in learning[0]] == [h for h, _ in learning[1]])
    oral_lengths = [len(body.strip()) for _, body in learning[1]]
    check("each_oral_step60_to100_characters", all(60 <= count <= 100 for count in oral_lengths), lengths=oral_lengths)

    links, missing = 0, []
    for name in sorted(DOCS):
        for value in re.findall(r"\[[^\]]*\]\(([^)]+)\)", (ROOT / name).read_text(encoding="utf-8")):
            value = value.split("#", 1)[0]
            if not value or re.match(r"^[a-zA-Z]+://", value):
                continue
            links += 1
            if not ((ROOT / name).parent / value).exists():
                missing.append({"document": name, "target": value})
    check("updated_document_local_links_resolve", not missing, checked=links, missing=missing)
    for name in CODE:
        if name.endswith(".py"):
            ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
    for name in REPORT_NAMES:
        read(CHECKS / name)
    check("acceptance_scripts_and_reports_parse", True)
    check("six_screenshots_match_raw_bytes", all(digest(CHECKS / target) == digest(OUT / "ui" / source) for source, target in SCREENSHOTS.items()))
    ignored = sorted(name for name in DOCS | ARTIFACTS if name not in baseline["files"])
    ignore = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], input="\0".join(ignored) + "\0", cwd=ROOT, text=True, capture_output=True, encoding="utf-8")
    check("new_local_docs_explicitly_checked_under_original_ignore", ignore.returncode == 0 and set(ignore.stdout.rstrip("\0").split("\0")) == set(ignored), count=len(ignored))

    paths = {p.relative_to(ROOT).as_posix(): p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "frontend/components", "frontend/tests", "configs", "docs") for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts}
    paths.update({"docs/checks/" + target: CHECKS / target for target in SCREENSHOTS.values()})
    delta = {name: path for name, path in paths.items() if name not in baseline["files"] or digest(path) != baseline["files"][name]}
    check("complete_scanned_delta_is_expected", set(delta) <= DOCS | CODE | ARTIFACTS, unexpected=sorted(set(delta) - DOCS - CODE - ARTIFACTS))
    check("all_expected_app_and_document_files_present", all((ROOT / name).is_file() for name in DOCS | CODE | ARTIFACTS))
    # Only read isolated random credentials in memory; never print them or read formal credentials.
    state = read(OUT / "ui/state.json")
    text_paths = [path for name, path in delta.items() if path.suffix != ".jpg"]
    check("no_isolated_password_copied_to_deliverables", all(password not in path.read_text(encoding="utf-8-sig") for password in state["passwords"].values() for path in text_paths))
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True)
    check("git_diff_check_passed", diff.returncode == 0)
    check("git_index_empty", not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip())
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").rstrip("\0")
    check("new_unignored_files_are_expected", set(untracked.split("\0") if untracked else []) <= CODE)
    ports = ps_json("@(Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess) | ConvertTo-Json -Compress")
    check("formal_ports_restored_8001_free", {row["LocalPort"] for row in ports} == {3000, 8000, 6333}, ports=ports)
    workers = ps_json("@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scripts/model_query_worker.py*' } | Select-Object ProcessId) | ConvertTo-Json -Compress")
    check("no_test_model_process_remaining", not workers)

    backend_log = (OUT / "backend-tests.log").read_text(encoding="utf-8-sig")
    algorithm_log = (OUT / "algorithm-contracts.log").read_text(encoding="utf-8-sig")
    frontend_log = (OUT / "frontend-tests-final2.log").read_text(encoding="utf-8-sig")
    build_log = (OUT / "build-final2.log").read_text(encoding="utf-8-sig")
    check("saved_final_test_logs_confirm_reported_counts", "Ran 75 tests in 29.435s" in backend_log and backend_log.rstrip().endswith("OK") and "4 passed in 2.39s" in algorithm_log and "pass 18" in frontend_log and "fail 0" in frontend_log and "306.7414" in frontend_log)
    check("saved_final_build_and_typecheck_logs_present", "Compiled successfully" in build_log and "Finalizing page optimization" in build_log and (OUT / "typecheck-final2.log").is_file())
    check("ten_queries_one_worker_zero_page_encoding", formal["query_count"] == 10 and formal["query_worker_pids"] == [41392] and formal["page_encoding_count"] == 0)
    write(doc_path, {"date": datetime.now().astimezone().isoformat(), "round": "R18", "overall": "passed", "checks": checks, "limits": "old-project snapshot covers Git/selected files/model packages; no ignored full-disk audit; application runs are prior evidence within this same R18, not rerun by this document pass"})
    modified = [{"path": name, "change": "modified" if name in baseline["files"] else "new", "sha256": None if path == report_path else digest(path)} for name, path in sorted(delta.items())]
    write(report_path, {
        "date": datetime.now().astimezone().isoformat(), "round": "R18", "stage": "2-3B-2", "overall": "passed",
        "scope": "dual-mode and authorized document picker frontend; no DB/API/backend/SDK/algorithm changes",
        "tests": {"backend": {"passed": 75, "seconds": 29.435}, "algorithm_CPU": {"passed": 4, "seconds": 2.39}, "frontend_final": {"passed": 18, "milliseconds": 306.7414}, "TypeScript": "passed", "production_build": "passed", "HTTP_metadata": 16, "browser": 65, "browser_build_phases": phases, "formal": 21, "document_protection": len(checks)},
        "actual_query_forwards": 10, "query_worker_pids": [41392], "network_attempts": 0, "page_encoding_count": 0,
        "query_limit": "includes one cancelled response and one dependency failure; not10 successful displays",
        "ports_at_document_check": ports,
        "source_evidence": ["runtime/verification/r18/backend-tests.log", "runtime/verification/r18/algorithm-contracts.log", "runtime/verification/r18/frontend-tests-final2.log", "runtime/verification/r18/typecheck-final2.log", "runtime/verification/r18/build-final2.log", "runtime/verification/r18/ui/browser-checks.json"],
        "modified_files": modified, "self_report_hash": "omitted to avoid recursive hash; all other manifest file hashes verified after write",
        "runtime_private_files": "local runtime/verification/r18 retained; random credential state and detailed logs excluded from public file manifest",
        "formal_credentials_read_used_changed": False, "git_stage_commit_push_executed": False,
        "unresolved_blockers": [], "next_unique_task": "2-3C: upload/jobs UI, recovery/retry including cancellation checkpoint; await user",
        "limits": read(CHECKS / "stage2-3b2-browser.json")["limits"],
    })
    final = read(report_path)
    if not all(item["sha256"] is None or digest(ROOT / item["path"]) == item["sha256"] for item in final["modified_files"]):
        raise AssertionError("Final manifest hash changed during generation")
    print(f"R18 complete: {len(checks)} document/protection checks; {len(modified)} explicit modified/new files; oral lengths {oral_lengths}; manifest hashes verified; no credentials printed")


if __name__ == "__main__":
    main()
