"""R15 final incremental file, documentation and protection verification. No GPU."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

from backend.db.connection import ROOT


def main():
    report_path = ROOT / "docs/checks/r15-document-checks.json"
    summary_path = ROOT / "docs/checks/stage2-2-verification.json"
    if report_path.exists() or summary_path.exists():
        raise RuntimeError("R15 final evidence already exists; choose a new report name instead of overwriting")
    checks = []

    def read(relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    before = read("docs/checks/stage2-2-preflight.json")
    existing_changed = sorted(p for p, value in before["files"].items()
                              if not (ROOT / p).is_file() or digest(ROOT / p) != value)
    intended = {
        "backend/main.py", "backend/db/models.py", "backend/db/seed.py", "backend/documents/ingest.py",
        "backend/search/scope.py", "backend/search/worker.py", "scripts/model_query_worker.py", "tests/test_uploads.py",
        "docs/AI交接.md", "docs/architecture.md", "docs/interfaces.md", "docs/progress.md", "docs/testing.md",
        "docs/阶段2新窗口接手指南.md", "docs/项目开发阶段规划与任务.md",
        "docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md",
    }
    check("only_intended_existing_files_changed_since_R15_baseline", set(existing_changed) == intended)
    protected = [p for p in before["files"] if p.startswith("docs/过程记录/0") and p.split("/")[-1][:2] in {"01", "02", "03", "04", "05", "06"}]
    check("all_six_historical_learning_files_present", len(protected) == 6)
    check("01_to_06_gitignore_AGENTS_exact_bytes_preserved", all(digest(ROOT / p) == before["files"][p] for p in protected + [".gitignore", "AGENTS.md"]))
    check("all_preexisting_reports_unchanged", all(digest(ROOT / p) == value for p, value in before["files"].items() if p.startswith("docs/checks/")))
    check("source_repositories_algorithms_config_and_model_environment_unchanged",
          read("docs/checks/source-state-r15-before.json") == read("docs/checks/source-state-r15-final.json"))
    check("frontend_and_dependency_files_unchanged_in_R15", all(digest(ROOT / p) == value for p, value in before["files"].items()
                                                                if p.startswith("frontend/") or p.startswith("requirements-")))

    expected_steps = [f"S{i:02}" for i in range(1, 6)]
    learning_paths = [ROOT / "docs/过程记录/07_2技术操作详解.md", ROOT / "docs/过程记录/08_2逐步口述稿.md"]
    headings = []
    speech_counts = {}
    for path in learning_paths:
        content = path.read_text(encoding="utf-8")
        found = re.findall(r"^## 2026-11-07｜R15｜2-2｜(S\d\d)：([^\n]+)$", content, re.M)
        check("five_matching_steps_" + path.name, [step for step, _ in found] == expected_steps)
        headings.append(found)
        prefix = content[:content.index("## 2026-11-07｜R15｜2-2｜S01")].rstrip() + "\n"
        # File writers may preserve Windows CRLF or normalize it to LF. The
        # complete historical content must match one of these encodings.
        prefix_hashes = {hashlib.sha256(x.encode("utf-8")).hexdigest() for x in (prefix, prefix + "\n", prefix.replace("\n", "\r\n"), (prefix + "\n").replace("\n", "\r\n"))}
        check("preexisting_R14_learning_content_preserved_" + path.name, before["files"][path.relative_to(ROOT).as_posix()] in prefix_hashes)
        if path == learning_paths[1]:
            for step, body in re.findall(r"^## 2026-11-07｜R15｜2-2｜(S\d\d)：[^\n]+\n(.*?)(?=^## |\Z)", content, re.M | re.S):
                speech_counts[step] = len(re.sub(r"\s", "", body))
    check("technical_and_speech_titles_match", headings[0] == headings[1])
    check("R15_speeches_60_to_100_characters", len(speech_counts) == 5 and all(60 <= n <= 100 for n in speech_counts.values()))

    current_paths = [p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "configs", "docs")
                     for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".json", ".md", ".css") and "__pycache__" not in p.parts]
    new_files = sorted(p.relative_to(ROOT).as_posix() for p in current_paths if p.relative_to(ROOT).as_posix() not in before["files"])
    # The baseline script existed at the moment it captured its own hash.
    increment = sorted(set(existing_changed + new_files + ["scripts/check_stage2_2_baseline.py", report_path.relative_to(ROOT).as_posix(), summary_path.relative_to(ROOT).as_posix()]))
    python_files = []
    for folder in ("backend", "scripts", "tests", "migrations"):
        for path in (ROOT / folder).rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8-sig"))
            python_files.append(path.relative_to(ROOT).as_posix())
    check("python_syntax", bool(python_files))
    local_links = 0
    utf8_files = 0
    for relative in increment:
        path = ROOT / relative
        if path in {report_path, summary_path}:
            continue
        content = path.read_text(encoding="utf-8-sig")
        utf8_files += 1
        if path.suffix == ".json":
            json.loads(content)
        if path.suffix != ".md":
            continue
        for _, target in re.findall(r"\[([^\]\n]*)\]\(([^\n)]+)\)", content):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("app:", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            check("local_link_" + relative + "_" + target, resolved.is_file() or resolved in {report_path, summary_path})
            local_links += 1
    check("git_diff_check", subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True).returncode == 0)
    old_staged = [line for line in before["existing_changes"] if line[0] not in {" ", "?"}]
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).decode().strip()
    check("no_staging_added", not old_staged and not staged)
    new_doc_paths = [relative for relative in increment if relative.startswith("docs/") and relative not in before["files"]]
    ignored = subprocess.run(["git", "check-ignore", "--", *new_doc_paths], cwd=ROOT, capture_output=True)
    check("new_docs_remain_ignored_under_existing_rule", ignored.returncode == 0 and len(ignored.stdout.decode("utf-8").splitlines()) == len(new_doc_paths))

    http = read("docs/checks/stage2-2-http-attempt2.json")
    formal = read("docs/checks/stage2-2-formal-final.json")
    reference = read("docs/checks/stage2-2-reference.json")
    check("real_HTTP_all_48_passed", http["status"] == "passed" and len(http["checks"]) == 48 and all(c["passed"] for c in http["checks"]))
    check("formal_all_20_passed", formal["status"] == "passed" and len(formal["checks"]) == 20 and all(c["passed"] for c in formal["checks"]))
    check("real_eight_page_four_query_forwards", http["model_page_forwards"] == 8 and http["model_query_forwards_before_restart"] == 4)
    check("four_reference_cases_eight_full_tensors", reference["status"] == "passed" and len(reference["cases"]) == 4 and len(reference["new_full_tensors"]) == 8)
    check("first_selection_failure_retained", read("docs/checks/stage2-2-http-attempt1.json")["status"] == "failed")
    check("final_63_backend_tests_passed", "Ran 63 tests in 25.749s\n\nOK" in (ROOT / "runtime/verification/r15/backend-final-after-error-code.log").read_text(encoding="utf-8"))

    report = {"date": "2026-11-07", "round": "R15", "stage": "2-2", "status": "passed", "checks": checks,
              "python_files": len(python_files), "utf8_increment_files": utf8_files, "local_file_links": local_links,
              "speech_characters": speech_counts, "preexisting_files_changed": existing_changed,
              "new_local_files_including_ignored": sorted(set(new_files + [report_path.relative_to(ROOT).as_posix(), summary_path.relative_to(ROOT).as_posix()])),
              "preserved_baseline_file_count": len(before["files"]) - len(existing_changed),
              "protection_limit": "old repositories inspectable Git state, selected algorithms/config/locks and model package inventory, not a full ignored-file audit"}
    summary = {"date": "2026-11-07", "round": "R15", "stage": "2-2", "status": "completed_within_scope",
               "next_only_task": "2-3A: authorized document list, literal name contains filter, single-document search backend/SDK; await user instruction",
               "incremental_changed_files": increment,
               "baseline": "docs/checks/stage2-2-preflight.json", "backup": "runtime/verification/r15/metadata-before.sqlite3",
               "tables_added": ["system_state", "page_features"], "public_API_schema_changed": False,
               "checks": {"backend_unittest": {"passed": 63, "seconds": 25.749, "log": "runtime/verification/r15/backend-final-after-error-code.log"},
                          "algorithm_CPU_contract_pytest": {"passed": 4, "seconds": 2.32, "log": "runtime/verification/r15/algorithm-tests.log"},
                          "frontend_node": {"passed": 4}, "frontend_typecheck": "passed", "production_build": "not rerun; frontend/API unchanged",
                          "real_HTTP": "docs/checks/stage2-2-http-attempt2.json (48)", "official_reference": "docs/checks/stage2-2-reference.json (4 cases)",
                          "formal_final": "docs/checks/stage2-2-formal-final.json (20)", "protection": "docs/checks/r15-document-checks.json"},
               "actual_GPU": {"page_forwards": 8, "query_forwards": 4, "same_worker_pid": http["single_model_worker_pid"], "network_attempts": 0},
               "max_reference_abs_difference": max(c["max_abs_diff"] for c in reference["cases"]),
               "formal_state": "0005; old 10 business/auth tables unchanged; original13 active; jobs/page_features empty; integrity ok/FK0",
               "visual_review": {"image": "runtime/verification/r15/real-attempt2/render-contact-sheet.png", "all_new_pages": 8, "observation": "no obvious clipping, missing pages or black blocks", "limit": "thumbnail QA, not OCR/region/coordinate accuracy"},
               "failures_preserved": ["stage2-2-http-attempt1.json: no new2-3-page fixture; stopped before GPU", "unit import duplicated10 older cases; corrected module import", "pypdf xref/object-stream warnings; source SHA unchanged", "temporary GBK decode inspection error corrected with explicit UTF-8", "document patch wrong heading rejected atomically; corrected scoped update"],
               "blockers_for_2_2": [],
               "limitations": ["copy-on-write full generations add storage/write amplification; only13+8-page sample verified", "private failed files/collections retained; cleanup/retry/cancel later", "completed restart real; running recovery/failure injection unit-simulated, not power cut", "real new uploads isolated; formal checks anonymous without formal credentials", "no UI, document list/single-document scope, MinerU, D, highlights, budget method, accuracy or capacity claims"],
               "runtime": formal["runtime"], "formal_credentials_used": False, "downloaded_models": False, "training": False,
               "git_staging_commit_or_push": False, "learning_records": [p.relative_to(ROOT).as_posix() for p in learning_paths]}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in (report_path, summary_path):
        check("final_output_readback_" + path.name, json.loads(path.read_text(encoding="utf-8"))["status"] in {"passed", "completed_within_scope"})
    print(json.dumps({"status": "passed", "python_files": len(python_files), "local_links": local_links,
                      "speech_characters": speech_counts, "incremental_files": len(increment)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
