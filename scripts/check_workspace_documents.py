"""Finish R17 evidence and explicit ignored-document protection checks; no app mutation."""
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

OUT = ROOT / "runtime/verification/r17"
CHECKS = ROOT / "docs/checks"
DOCS = {
    "docs/AI交接.md", "docs/progress.md", "docs/testing.md", "docs/architecture.md",
    "docs/interfaces.md", "docs/requirements.md", "docs/前端工作台改版方案与复用评估.md",
    "docs/项目开发阶段规划与任务.md", "docs/阶段2新窗口接手指南.md",
    "docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md",
}
CODE = {
    "frontend/app/page.tsx", "frontend/app/workspace.css", "frontend/components/workspace/workspace.tsx",
    "frontend/tests/workspace-components.test.cjs", "scripts/check_workspace_acceptance.py",
    "scripts/workspace_acceptance_server.py", "scripts/check_workspace_documents.py",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report_path = CHECKS / "stage2-3b1-verification.json"
    doc_path = CHECKS / "r17-document-checks.json"
    if report_path.exists() or doc_path.exists():
        raise RuntimeError("R17 final report already exists; preserve it")
    baseline = read(CHECKS / "stage2-3b1-preflight.json")
    formal = read(CHECKS / "stage2-3b1-formal.json")
    browser = read(OUT / "ui/browser-checks.json")
    events = [json.loads(line) for line in (OUT / "ui/http-observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    browser_report = {
        "date": datetime.now().astimezone().isoformat(), "round": "R17", "overall": "passed",
        "checks": browser, "http_search_status_counts": dict(Counter(str(e["status"]) for e in events if e["path"] == "/search")),
        "authorized_png_responses": sum(e["path"].startswith("/pages/") and e["status"] == 200 for e in events),
        "data": "isolated R15 completed21 clone; random credentials and explicit long-name/permission fixtures",
        "faults": "6s response delay and metadata change before recheck are test-only injections; Qdrant connection refused on isolated adapter; formal Qdrant untouched",
        "limits": ["no automatic password change", "no new BFCache experiment", "PNG permission404 verified; no interrupted-transfer/corrupt-PNG retry experiment", "no capacity or full accessibility audit", "no dual-mode or document picker UI"],
    }
    if not (CHECKS / "stage2-3b1-browser.json").exists():
        write(CHECKS / "stage2-3b1-browser.json", browser_report)
    write(CHECKS / "stage2-3b1-failures.json", {"round": "R17", "unresolved": [], "records": [
        {"issue": "Initial tsc cwd and later helper module cwd were wrong", "effect": "Commands did not execute their intended target; no app state changed", "resolution": "Use frontend for Node/Next and root for Python modules; final checks passed"},
        {"issue": "Initial frontend process guard expected next-server", "effect": "Guard refused stop; actual process was project next start", "resolution": "Reread CIM command/parent/creation time; narrow guard corrected before stopping"},
        {"issue": "Sidebar exact width80 comparison saw79.99588775634766", "evidence": "runtime/verification/r17/ui/browser-checks-first-pass.json", "resolution": "Preserve first observation; use1px layout tolerance; no CSS change to force a number"},
        {"issue": "Generic alert/notice observation occurred before async409 arrived", "resolution": "Observe workspace notice and actual HTTP status after response; no authorization change"},
        {"issue": "Collapsed mobile navigation note/focus and shared-busy logout wording needed refinement", "resolution": "Hide note, Enter focuses New Search, Escape returns focus, separate logout status; final build/SSR/browser checked"},
        {"issue": "Narrow preview could hide a later permission/scope warning in the results view", "resolution": "On notice switch to search view and restore focus after render; each submit selects search; append real PNG404 browser check and rebuild"},
        {"issue": "Existing baseline-browser-mapping age warning", "resolution": "Build passed; no dependency upgrade"},
        {"issue": "Read-only rg probes used a few nonexisting candidate filenames", "resolution": "Read actual listed files; not an application failure"},
        {"issue": "Document link checker ran before creating its own report", "evidence": "docs/checks/r17-document-checks-attempt1.json", "resolution": "Preserve failed report and building summary as attempt1; create current report before checking self-links, then replace building status only after checks pass"},
    ]})
    for source, target in (("final-wide-results.jpg", "stage2-3b1-wide.jpg"), ("final-laptop-results.jpg", "stage2-3b1-laptop.jpg"), ("final-narrow-preview.jpg", "stage2-3b1-narrow.jpg"), ("postfix-laptop-results.jpg", "stage2-3b1-laptop-final.jpg"), ("postfix-preview-access-changed.jpg", "stage2-3b1-access-changed.jpg")):
        destination = CHECKS / target
        if destination.exists():
            if digest(destination) != digest(OUT / "ui" / source):
                raise RuntimeError("Different screenshot exists; refusing overwrite")
        else:
            shutil.copyfile(OUT / "ui" / source, destination)

    write(report_path, {"overall": "building", "round": "R17"})
    write(doc_path, {"overall": "building", "round": "R17"})
    checks = []
    def check(name, value, **detail):
        checks.append({"name": name, "passed": bool(value), **detail})
        if not value:
            write(doc_path, {"overall": "failed", "round": "R17", "checks": checks})
            raise AssertionError(name)

    check("all30_browser_checks_passed", len(browser) == 30 and all(item["passed"] for item in browser))
    check("all14_formal_checks_passed", len(formal["checks"]) == 14 and all(item["passed"] for item in formal["checks"]))
    check("formal_database_still_equals_opening_snapshot_after_browser_reconnect", snapshot(DEFAULT_DATABASE) == baseline["database"])
    check("old_project_heads_changes_selected_algorithm_files_and_model_environment_unchanged", read(CHECKS / "source-state-r17-before.json") == read(CHECKS / "source-state-r17-final2.json"))
    check("web_python_packages_unchanged", sorted([d.metadata["Name"], d.version] for d in metadata.distributions()) == baseline["web_packages"])
    old_changed = [name for name, sha in baseline["files"].items() if not (ROOT / name).is_file() or digest(ROOT / name) != sha]
    check("only_intended_preexisting_files_changed", set(old_changed) <= DOCS | CODE, changed=old_changed)
    histories = [name for name in baseline["files"] if name.startswith("docs/过程记录/0") and not name.startswith(("docs/过程记录/07_", "docs/过程记录/08_"))]
    check("history01_06_original_bytes_preserved", bool(histories) and all(digest(ROOT / name) == baseline["files"][name] for name in histories), count=len(histories))
    check("all_preexisting_check_reports_unchanged", all(digest(ROOT / name) == sha for name, sha in baseline["files"].items() if name.startswith("docs/checks/")))
    check("gitignore_original_bytes_preserved", digest(ROOT / ".gitignore") == baseline["files"][".gitignore"])
    ignore = subprocess.run(["git", "check-ignore", "-v", "docs/stage2-3b1-runbook.md", "docs/过程记录/07_2技术操作详解.md"], cwd=ROOT, capture_output=True)
    check("ignored_local_deliverables_explicitly_checked", ignore.returncode == 0 and (ROOT / "docs/stage2-3b1-runbook.md").is_file())

    learning = []
    for name in ("docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md"):
        data = (ROOT / name).read_bytes()
        prefix = data.split("## 2026-11-07｜R17｜".encode())[0].rstrip(b"\r\n")
        candidates = [prefix + ending for ending in (b"\n", b"\r\n", b"\n\n", b"\r\n\r\n")]
        check("prior_learning_content_preserved_" + Path(name).name[:2], any(hashlib.sha256(candidate).hexdigest() == baseline["files"][name] for candidate in candidates))
        text = (ROOT / name).read_text(encoding="utf-8")
        parts = re.findall(r"^## (2026-11-07｜R17｜2-3B-1｜S\d+：[^\n]+)\n\n(.*?)(?=\n## |\Z)", text, re.M | re.S)
        check("five_R17_steps_" + Path(name).name[:2], len(parts) == 5)
        learning.append(parts)
    check("technical_oral_dates_rounds_steps_pair", [h for h, _ in learning[0]] == [h for h, _ in learning[1]])
    oral_lengths = [len(body.strip()) for _, body in learning[1]]
    check("each_oral_step60_to100_characters", all(60 <= count <= 100 for count in oral_lengths), lengths=oral_lengths)

    missing, links = [], 0
    for name in sorted(DOCS | {"docs/stage2-3b1-runbook.md"}):
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
    check("new_acceptance_scripts_parse", True)
    state = read(OUT / "ui/state.json")
    deliverables = DOCS | CODE | {"docs/stage2-3b1-runbook.md", "docs/checks/stage2-3b1-browser.json", "docs/checks/stage2-3b1-failures.json"}
    check("isolated_credentials_not_copied_into_code_or_documents", all(password not in (ROOT / name).read_text(encoding="utf-8") for password in state["passwords"].values() for name in deliverables))

    command = "@(Get-NetTCPConnection -State Listen -LocalPort 3000,8000,8001,6333 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess) | ConvertTo-Json -Compress"
    ports = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True))
    check("formal_ports_restored_and8001_free", {row["LocalPort"] for row in ports} == {3000, 8000, 6333})
    workers = subprocess.check_output(["powershell", "-NoProfile", "-Command", "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scripts/model_query_worker.py*' } | Select-Object ProcessId) | ConvertTo-Json -Compress"], text=True).strip()
    check("no_acceptance_model_tree_remaining", not workers or workers == "[]")
    check("backend_sdk_schema_dependencies_and_auth_css_not_edited", all(digest(ROOT / name) == sha for name, sha in baseline["files"].items() if name.startswith(("backend/", "migrations/", "frontend/lib/", "configs/", "requirements-")) or name in ("frontend/app/globals.css", "frontend/package.json", "frontend/yarn.lock")))
    write(doc_path, {"date": datetime.now().astimezone().isoformat(), "round": "R17", "overall": "passed", "checks": checks, "limits": "old-project snapshot covers Git/selected files/model packages, not ignored full-disk content"})

    paths = {p.relative_to(ROOT).as_posix(): p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "frontend/components", "frontend/tests", "configs", "docs") for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts}
    for name in ("docs/checks/stage2-3b1-wide.jpg", "docs/checks/stage2-3b1-laptop.jpg", "docs/checks/stage2-3b1-narrow.jpg", "docs/checks/stage2-3b1-laptop-final.jpg", "docs/checks/stage2-3b1-access-changed.jpg"):
        paths[name] = ROOT / name
    modified = [{"path": name, "change": "modified" if name in baseline["files"] else "new", "sha256": None if path == report_path else digest(path)} for name, path in sorted(paths.items()) if name not in baseline["files"] or digest(path) != baseline["files"][name]]
    versions = {name: read(ROOT / "frontend/node_modules" / name / "package.json")["version"] for name in ("next", "react", "react-dom", "typescript")}
    write(report_path, {"date": datetime.now().astimezone().isoformat(), "round": "R17", "stage": "2-3B-1", "overall": "passed", "scope": "workspace shell/presentation only; no DB/API/SDK/algorithm changes", "tests": {"backend": {"passed": 75, "seconds": 28.629}, "algorithm_cpu": {"passed": 4, "seconds": 2.28}, "frontend": {"passed": 9, "milliseconds": 269.0387}, "tsc": "passed", "production_build": "passed", "latest_logs": ["runtime/verification/r17/frontend-tests-preview-focus.log", "runtime/verification/r17/typecheck-preview-focus.log", "runtime/verification/r17/build-preview-focus.log"], "browser": 30, "formal": 14, "documents": len(checks)}, "real_query_count": formal["query_count"], "model_pids": formal["query_model_pids"], "page_encoding_count": 0, "node": subprocess.check_output(["node", "--version"], text=True).strip(), "installed_frontend_packages": versions, "ports": ports, "modified_files": modified, "self_report_hash": "omitted to avoid recursive hash", "next_unique_task": "2-3B-2: dual-mode and authorized document picker UI; await user", "unresolved_blockers": [], "formal_credentials_used_or_changed": False, "git_stage_commit_push_executed": False, "docs_ignore_preserved": True, "limits": ["no new official scoring run because algorithm unchanged", "fault timings explicitly injected in isolated backend", "no new BFCache/full accessibility/capacity audit", "dual-mode/upload/history/D remain later batches"]})
    print(f"R17 complete: {len(checks)} document/protection checks, {len(modified)} explicit changed/new files, oral lengths {oral_lengths}; no credentials printed")


if __name__ == "__main__":
    main()
