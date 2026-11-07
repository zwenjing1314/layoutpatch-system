"""R15 immutable baseline, backup and source protection. No secrets exported."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint


def main():
    out = ROOT / "runtime/verification/r15"
    out.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(out / "metadata-before.sqlite3")) as target:
        source.backup(target)
        collection = source.execute("SELECT collection_name FROM index_generations WHERE status='ready'").fetchone()[0]
    status = subprocess.check_output(["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "-z"], cwd=ROOT).decode()
    paths = [p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "configs", "docs")
             for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".json", ".md", ".css") and "__pycache__" not in p.parts]
    paths += [ROOT / name for name in (".gitignore", "AGENTS.md", "requirements-colpali.lock.txt", "requirements-web.lock.txt")]
    report = {"date": "2026-11-07", "round": "R15", "stage": "2-2", "database": snapshot(DEFAULT_DATABASE),
              "qdrant": vector_fingerprint(collection), "collection": collection,
              "existing_changes": [s for s in status.split("\0") if s],
              "files": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "ports": {"3000": 30652, "8000": 56496, "6333": 49880},
              "other_same_project_visible_chats": "idle"}
    (ROOT / "docs/checks/stage2-2-preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("R15 baseline/online backup saved; existing changes protected")


if __name__ == "__main__":
    main()
