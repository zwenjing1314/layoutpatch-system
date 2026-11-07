"""Read-only baseline and online SQLite backup; never export credentials."""
from contextlib import closing
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sqlite3

from backend.db.connection import ROOT, DEFAULT_DATABASE


def snapshot(path):
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {"revision": db.execute("SELECT version_num FROM alembic_version").fetchone()[0],
                "integrity": db.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_key_errors": len(db.execute("PRAGMA foreign_key_check").fetchall()),
                "tables": {table: {"count": db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0],
                    "sha256": hashlib.sha256(json.dumps(sorted(db.execute(f'SELECT * FROM "{table}"').fetchall()),
                        ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()} for table in tables}}


if __name__ == "__main__":
    destination = ROOT / "runtime/verification/r14"
    destination.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(destination / "metadata-before.sqlite3")) as target:
        source.backup(target)
    protected = [ROOT / ".gitignore", *sorted((ROOT / "docs/过程记录").glob("0[1-6]*"))]
    report = {"date": "2026-11-07", "round": "R14", "stage": "2-1", "database": snapshot(DEFAULT_DATABASE),
              "web_packages": sorted((d.metadata["Name"], d.version) for d in metadata.distributions()),
              "protected": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},
              "working_tree_before": "clean", "other_project_chats": "visible other same-project chats idle",
              "ports": {"3000": 38744, "8000": 6240, "6333": 49880}}
    (ROOT / "docs/checks/stage2-1-preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("R14 baseline and online backup saved; no credentials exported")
