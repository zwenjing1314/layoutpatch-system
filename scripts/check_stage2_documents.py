"""R14 final document, syntax and read-only protection checks; no model execution."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

from backend.db.connection import ROOT


def main():
    checks = []

    def read(path):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})
        if not value:
            raise AssertionError(name)

    before = read("docs/checks/stage2-1-preflight.json")
    check("01_to_06_and_gitignore_same_bytes", all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == value
                                                for p, value in before["protected"].items()))
    check("source_repositories_algorithm_and_model_environment_unchanged",
          read("docs/checks/source-state-r14-before.json") == read("docs/checks/source-state-r14-after.json"))
    syntax = []
    for directory in ("backend", "scripts", "tests", "migrations"):
        for path in (ROOT / directory).rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8-sig"))
            syntax.append(path.relative_to(ROOT).as_posix())
    check("python_syntax", bool(syntax))
    manuscripts = [ROOT / "docs/过程记录/07_2技术操作详解.md", ROOT / "docs/过程记录/08_2逐步口述稿.md"]
    expected = [f"S{i:02}" for i in range(1, 6)]
    for path in manuscripts:
        check("learning_steps_" + path.name, re.findall(r"^## 2026-11-07｜R14｜2-1｜(S\d\d)：", path.read_text(encoding="utf-8"), re.M) == expected)
    counts = []
    for section in re.split(r"^## .*\n", manuscripts[1].read_text(encoding="utf-8"), flags=re.M)[1:]:
        counts.append(len(re.sub(r"\s", "", section)))
    check("five_speech_texts_60_to_100_chars", len(counts) == 5 and all(60 <= count <= 100 for count in counts))
    ignored = subprocess.run(["git", "check-ignore", "--", *[str(p.relative_to(ROOT)) for p in manuscripts]], cwd=ROOT, capture_output=True)
    check("07_08_remain_locally_ignored", ignored.returncode == 0 and len(ignored.stdout.decode("utf-8").splitlines()) == 2)
    status = subprocess.check_output(["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "-z"], cwd=ROOT).decode("utf-8")
    changed = sorted(item[3:].replace("\\", "/") for item in status.split("\0") if item)
    links = 0
    for relative in [p for p in changed if p.endswith(".md")] + [p.relative_to(ROOT).as_posix() for p in manuscripts]:
        path = ROOT / relative
        for label, target in re.findall(r"\[([^\]\n]*)\]\(([^\n)]+)\)", path.read_text(encoding="utf-8")):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("app:", "mailto:")):
                continue
            check("link_" + relative + "_" + target, (path.parent / target).exists())
            links += 1
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True)
    check("git_diff_check", diff.returncode == 0)
    check("real_http_29_passed", read("docs/checks/stage2-1-http-attempt2.json")["status"] == "passed"
          and len(read("docs/checks/stage2-1-http-attempt2.json")["checks"]) == 29)
    check("formal_18_passed", read("docs/checks/stage2-1-formal.json")["status"] == "passed"
          and len(read("docs/checks/stage2-1-formal.json")["checks"]) == 18)
    check("first_http_failure_retained", read("docs/checks/stage2-1-http.json")["status"] == "failed")
    report = {"date": "2026-11-07", "round": "R14", "stage": "2-1", "status": "passed", "checks": checks,
              "python_files": len(syntax), "local_file_links": links, "speech_characters": dict(zip(expected, counts)),
              "protection_limit": "old repositories inspectable Git state and selected tracked/config/model environment; not full ignored-file audit"}
    (ROOT / "docs/checks/r14-document-checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(set(changed + ["docs/checks/stage2-1-verification.json", "docs/checks/r14-document-checks.json"] +
                       [p.relative_to(ROOT).as_posix() for p in manuscripts]))
    summary = {"date": "2026-11-07", "round": "R14", "stage": "2-1", "status": "completed_within_scope",
               "next_only_task": "R15 / 2-2: full page rendering/encoding and safe index activation; await user instruction",
               "changed_files": files,
               "checks": {"backend_unittest": {"passed": 55, "seconds": 18.763, "log": "runtime/verification/r14/backend-final2.log"},
                          "algorithm_contract_pytest": {"passed": 4, "seconds": 4.89, "log": "runtime/verification/r14/algorithm-tests.log", "gpu_forward": False},
                          "frontend_node": {"passed": 4}, "typecheck": "passed", "openapi_sdk_generation": "passed", "production_build": "passed",
                          "real_http_restart": "stage2-1-http-attempt2.json (29 checks)", "formal_migration_proxy": "stage2-1-formal.json (18 checks)",
                          "documents_and_protection": "r14-document-checks.json"},
               "failures_preserved": ["tests-first.log: discovery environment, old route list, filename expectation",
                    "uploads-second.log: Starlette base HTTP exception needed", "frontend initial cwd error corrected; command output retained in chat",
                    "stage2-1-http.json: acceptance script ambiguous join; second attempt separate directory"],
               "blockers_for_2_1": [],
               "limitations": ["queued only; no page encoding, MinerU, D, highlighting or upload UI", "no new GPU retrieval/reference comparison",
                    "no retry/cancel APIs", "pending render profile marker must be replaced with real render identity in 2-2",
                    "process restart checks, not power-cut or long-term concurrency", "filesystem/DB not one transaction; crash residue private and inactive",
                    "authenticated upload direct isolated HTTP; production proxy anonymous boundary only", "full page features preserved; no budget algorithm implemented"],
               "runtime": {"frontend_port": 3000, "frontend_pid": 30652, "backend_port": 8000, "backend_pid": 56496,
                           "qdrant_port": 6333, "qdrant_listener_pid": 49880, "isolated_8001": "stopped"},
               "formal_credentials_used": False, "downloaded_models": False, "training": False, "git_commit_or_push": False}
    (ROOT / "docs/checks/stage2-1-verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "python_files": len(syntax), "links": links, "speech_characters": counts,
                      "changed_files_including_local_learning": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
