"""R16 final evidence, incremental file inventory and preserved-boundary checks; no model."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

from backend.db.connection import ROOT
from backend.main import app


def main():
    summary_path = ROOT / "docs/checks/stage2-3a-verification.json"
    report_path = ROOT / "docs/checks/r16-document-checks.json"
    if summary_path.exists() or report_path.exists():
        raise RuntimeError("Final R16 outputs exist; choose new evidence paths")
    checks = []
    def read(p): return json.loads((ROOT / p).read_text(encoding="utf-8"))
    def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        if not condition: raise AssertionError(name)
    before = read("docs/checks/stage2-3a-preflight.json")
    changed = sorted(p for p, h in before["files"].items() if not (ROOT / p).is_file() or digest(ROOT / p) != h)
    allowed = {"backend/main.py", "backend/db/models.py", "backend/db/seed.py", "backend/documents/access.py", "backend/search/routes.py", "backend/search/scope.py", "tests/test_auth.py",
               "frontend/lib/api/generated/index.ts", "frontend/lib/api/generated/models/SearchResponse.ts", "frontend/lib/api/generated/services/DocumentsService.ts", "frontend/lib/api/generated/services/SearchService.ts",
               "docs/AI交接.md", "docs/architecture.md", "docs/interfaces.md", "docs/progress.md", "docs/requirements.md", "docs/testing.md",
               "docs/前端工作台改版方案与复用评估.md", "docs/单文档检索功能设计与分批计划.md", "docs/阶段2新窗口接手指南.md", "docs/项目开发阶段规划与任务.md",
               "docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md"}
    check("only_intended_existing_files_changed", set(changed) == allowed)
    protected = [p for p in before["files"] if p.startswith("docs/过程记录/") and p.split("/")[-1][:2] in {"01", "02", "03", "04", "05", "06"}]
    check("six_old_learning_files_and_ignore_rules_exactly_preserved", len(protected) == 6 and all(digest(ROOT / p) == before["files"][p] for p in protected + [".gitignore", "AGENTS.md"]))
    check("all_old_reports_preserved", all(digest(ROOT / p) == h for p, h in before["files"].items() if p.startswith("docs/checks/")))
    check("source_repositories_original_algorithms_config_model_environment_unchanged", read("docs/checks/source-state-r16-before.json") == read("docs/checks/source-state-r16-final.json"))
    check("frontend_app_and_dependency_files_unchanged", all(digest(ROOT / p) == h for p, h in before["files"].items() if p.startswith(("frontend/app/", "requirements-")) or p in {"frontend/package.json", "frontend/yarn.lock"}))
    check("existing_client_auth_and_core_SDK_unchanged", all(digest(ROOT / p) == h for p, h in before["files"].items() if p.startswith("frontend/lib/") and p not in allowed))
    check("SDK_new_models_present", all((ROOT / ("frontend/lib/api/generated/models/" + n + ".ts")).is_file() for n in ("DocumentListItem", "DocumentListResponse")))
    check("OpenAPI_matches_running_source", read("frontend/docs/openapi.json") == app.openapi())
    previous_schema = json.loads(subprocess.check_output(["git", "show", "HEAD:frontend/docs/openapi.json"], cwd=ROOT).decode("utf-8"))
    current_schema = app.openapi()
    check("old_public_routes_preserved", set(current_schema["paths"]) - set(previous_schema["paths"]) == {"/documents"} and set(previous_schema["paths"]) <= set(current_schema["paths"]))
    check("all_old_hit_fields_preserved", previous_schema["components"]["schemas"]["SearchHit"] == current_schema["components"]["schemas"]["SearchHit"])
    old_props = previous_schema["components"]["schemas"]["SearchResponse"]["properties"]
    new_props = current_schema["components"]["schemas"]["SearchResponse"]["properties"]
    check("SearchResponse_only_adds_mode_and_target", set(new_props) - set(old_props) == {"search_mode", "document_id"} and all(new_props[k] == v for k,v in old_props.items()))
    expected = [f"S{i:02}" for i in range(1,6)]
    titles, counts = [], {}
    learning = ["docs/过程记录/07_2技术操作详解.md", "docs/过程记录/08_2逐步口述稿.md"]
    for relative in learning:
        content = (ROOT / relative).read_text(encoding="utf-8")
        found = re.findall(r"^## 2026-11-07｜R16｜2-3A｜(S\d\d)：([^\n]+)$", content, re.M)
        check("five_steps_" + relative, [step for step,_ in found] == expected)
        titles.append(found)
        prefix = content[:content.index("## 2026-11-07｜R16｜2-3A｜S01")].rstrip() + "\n"
        variants = (prefix, prefix+"\n", prefix.replace("\n", "\r\n"), (prefix+"\n").replace("\n", "\r\n"))
        check("all_previous_learning_content_preserved_" + relative, before["files"][relative] in {hashlib.sha256(v.encode()).hexdigest() for v in variants})
        if relative == learning[1]:
            counts = {step: len(re.sub(r"\s", "", body)) for step,body in re.findall(r"^## 2026-11-07｜R16｜2-3A｜(S\d\d)：[^\n]+\n(.*?)(?=^## |\Z)", content, re.M|re.S)}
    check("technical_speech_titles_match", titles[0] == titles[1])
    check("all_five_speeches_60_to_100_chars", len(counts) == 5 and all(60 <= count <= 100 for count in counts.values()))
    new = sorted(p.relative_to(ROOT).as_posix() for folder in ("backend", "scripts", "tests", "migrations", "frontend/lib", "frontend/tests", "docs")
                 for p in (ROOT/folder).rglob("*") if p.is_file() and p.suffix in {".py", ".md", ".json", ".ts", ".cjs"} and "__pycache__" not in p.parts and p.relative_to(ROOT).as_posix() not in before["files"])
    outputs = [p.relative_to(ROOT).as_posix() for p in (summary_path, report_path)]
    increment = sorted(set(changed + new + outputs + ["frontend/docs/openapi.json", "scripts/check_selection_preflight.py", "docs/checks/source-state-r16-before.json"]))
    python_count = 0
    for folder in ("backend", "scripts", "tests", "migrations"):
        for p in (ROOT/folder).rglob("*.py"):
            ast.parse(p.read_text(encoding="utf-8-sig")); python_count += 1
    check("all_project_Python_syntax", python_count > 0)
    links = 0
    for relative in increment:
        path = ROOT / relative
        if path in {summary_path, report_path}: continue
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix == ".json": json.loads(text)
        if path.suffix != ".md": continue
        for _,target in re.findall(r"\[([^\]\n]*)\]\(([^\n)]+)\)", text):
            target = target.strip("<>").split("#",1)[0]
            if not target or "://" in target or target.startswith(("app:", "mailto:")): continue
            resolved = (path.parent / target).resolve()
            check("link_"+relative+"_"+target, resolved.is_file() or resolved in {summary_path, report_path}); links += 1
    check("git_diff_check", subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True).returncode == 0)
    check("no_git_staging", not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).decode().strip()
          and not any(line[0] not in {" ", "?"} for line in before["existing_changes"]))
    ignored = [p for p in new+outputs if p.startswith("docs/")]
    ignore_check = subprocess.run(["git", "check-ignore", "--", *ignored], cwd=ROOT, capture_output=True)
    check("new_docs_preserve_existing_ignore_rule", ignore_check.returncode == 0 and len(ignore_check.stdout.decode("utf-8").splitlines()) == len(ignored))
    http, reference, formal = [read(p) for p in ("docs/checks/stage2-3a-http-attempt2.json", "docs/checks/stage2-3a-reference.json", "docs/checks/stage2-3a-formal.json")]
    check("real_HTTP94_passed", http["status"] == "passed" and len(http["checks"]) == 94 and all(c["passed"] for c in http["checks"]))
    check("formal27_passed", formal["status"] == "passed" and len(formal["checks"]) == 27 and all(c["passed"] for c in formal["checks"]))
    check("reference6_scope_cases_passed", reference["status"] == "passed" and len(reference["cases"]) == 6 and all(c["top_k_matches"] for c in reference["cases"]))
    check("six_query_zero_page_forwards", http["real_query_forwards"] == 6 and http["page_forwards"] == 0 and http["network_attempts"] == 0)
    check("first_failures_retained", read("docs/checks/stage2-3a-http-attempt1.json")["status"] == "failed" and read("docs/checks/r16-formal-first-failure.json")["status"] == "failed_acceptance_assertion")
    logs = ROOT / "runtime/verification/r16"
    check("backend75_passed", "Ran 75 tests in 30.352s\n\nOK" in (logs / "backend-final.log").read_text(encoding="utf-8"))
    check("algorithm4_passed", "4 passed in 2.26s" in (logs / "algorithm-tests.log").read_text(encoding="utf-8"))
    check("frontend5_typecheck_build_passed", "pass 5" in (logs / "frontend-tests.log").read_text(encoding="utf-8") and not (logs / "typecheck.log").read_text().strip()
          and "Compiled successfully" in (logs / "frontend-build.log").read_text(encoding="utf-8"))
    report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "passed", "checks": checks,
              "python_files": python_count, "local_file_links": links, "speech_characters": counts,
              "existing_files_changed": changed, "new_local_files_including_ignored": sorted(set(new+outputs)),
              "protection_limit": "old repositories inspectable Git state plus selected algorithms/config/lock/model package inventory; not full ignored-file audit"}
    summary = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "status": "completed_within_scope", "incremental_changed_files": increment,
               "next_only_task": "2-3B-1: workspace shell and presentation components; preserve real library search/auth/image lifecycle; await user instruction",
               "database_change": "0006 documents.display_name_key and index only; NFKC+casefold backfill; all old columns/other11 tables unchanged",
               "API": {"new": "GET /documents", "extended": "GET /search optional UUID document_id", "response_added": ["search_mode", "document_id"], "SDK_generated": True},
               "checks": {"backend": {"passed":75,"seconds":30.352,"log":"runtime/verification/r16/backend-final.log"}, "algorithm_CPU_contract": {"passed":4,"seconds":2.26},
                          "frontend_node":5,"typecheck":"passed","SDK_generation":"passed","production_build":"passed",
                          "real_HTTP":"docs/checks/stage2-3a-http-attempt2.json (94)","reference":"docs/checks/stage2-3a-reference.json (6)",
                          "formal":"docs/checks/stage2-3a-formal.json (27)","documents":"docs/checks/r16-document-checks.json"},
               "real_model": {"query_forwards":6,"page_forwards":0,"same_worker_pid":http["worker_pid"],"network_attempts":0},
               "max_reference_abs_difference":max(c["max_abs_diff"] for c in reference["cases"]),
               "scope_evidence":"A library9 pages, selected original5/new4; actual Qdrant filter/page/versions before Top-k and full index count21; higher-score other doc excluded",
               "preserved":"formal original13 vectors/config/payload, R15 completed21 collection,8 full BF16 tensors and R15 source DB unchanged; old learning/reports/ignore rules retained",
               "failures_preserved":["static compile missing parentheses fixed before tests", "HTTP attempt1 old fixed13 fingerprint rejects21 before GPU; dynamic check used in separate attempt2", "production Vary assertion expected single value, corrected standard token check; response protection already correct"],
               "blockers_for_2_3A":[],"limits":["server pagination snapshot is O(visible metadata/pages), not large-corpus performance claim", "searchable means DB/index metadata eligibility, not live GPU/Qdrant health", "mid-inference revocation tests use doubles; HTTP withdrawal occurs between requests", "no UI/workspace, upload retry/cancel, MinerU/D/highlights, accuracy/capacity or page re-encoding"],
               "runtime":formal["runtime"],"formal_credentials_used":False,"downloaded_models":False,"training":False,"git_staging_commit_or_push":False,
               "learning_records":learning}
    for path,payload in ((report_path,report),(summary_path,summary)):
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))["status"] in {"passed","completed_within_scope"}
    print(json.dumps({"status":"passed","Python_files":python_count,"local_links":links,"speech_characters":counts,"incremental_files":len(increment)},ensure_ascii=False))


if __name__ == "__main__":
    main()
