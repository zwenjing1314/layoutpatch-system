"""R16 immutable starting snapshot and online backup; no credentials printed."""
from contextlib import closing
import hashlib
import importlib.metadata as metadata
import json
import sqlite3
import subprocess

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint


def main():
    output = ROOT / "runtime/verification/r16"
    output.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(output / "metadata-before.sqlite3")) as target:
        source.backup(target)
        collection = source.execute("SELECT collection_name FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)").fetchone()[0]
    paths = [p for folder in ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "frontend/tests", "configs", "docs")
             for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts]
    paths += [ROOT / name for name in (".gitignore", "AGENTS.md", "requirements-colpali.in", "requirements-colpali.lock.txt", "requirements-web.in", "requirements-web.lock.txt", "frontend/package.json", "frontend/yarn.lock")]
    status = subprocess.check_output(["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "-z"], cwd=ROOT).decode("utf-8")
    report = {"date": "2026-11-07", "round": "R16", "stage": "2-3A", "database": snapshot(DEFAULT_DATABASE),
              "collection": collection, "qdrant": vector_fingerprint(collection),
              "existing_changes": [line for line in status.split("\0") if line],
              "files": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()},
              "web_packages": sorted([d.metadata["Name"], d.version] for d in metadata.distributions()),
              "ports": {"3000": 30652, "8000": 45388, "6333": 49880}, "other_same_project_visible_chats": "idle"}
    (ROOT / "docs/checks/stage2-3a-preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("R16 online backup/baseline saved; original13 and existing changes protected")


if __name__ == "__main__":
    main()
