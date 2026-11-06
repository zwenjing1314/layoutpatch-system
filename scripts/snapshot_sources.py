"""Read-only boundary snapshot, excluding ignored source files."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
result = {}
for name in ("layoutpatch", "layoutpatch-evidence", "Snappy"):
    source = root.parent / name
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args]).decode("utf-8")
    changes = git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    result[name] = {"head": git("rev-parse", "HEAD").strip(), "changes": [
        {"status": item[:2], "path": item[3:], "sha256": hashlib.sha256((source / item[3:]).read_bytes()).hexdigest()
         if (source / item[3:]).is_file() else None} for item in changes if item
    ]}
result["protected_files"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in [*sorted((root / "backend/algorithms").glob("*.py")), root / "requirements-colpali.lock.txt", root / "requirements-colpali.in", root / "configs/colpali_local.json"]}
result["model_environment"] = subprocess.check_output([str(root / ".venv/Scripts/python.exe"), "-c",
    "import importlib.metadata as m,json; print(json.dumps(sorted((d.metadata['Name'],d.version) for d in m.distributions())))"]).decode().strip()
round_id = sys.argv[2] if len(sys.argv) > 2 else "r05"
target = root / "docs/checks" / f"source-state-{round_id}-{sys.argv[1]}.json"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target.name)
