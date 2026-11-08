"""R20 read-only source/resource inventory and online formal database backup."""
from contextlib import closing
import hashlib
import importlib.metadata as metadata
import json
import os
import sqlite3
import subprocess

from backend.db.connection import ROOT, DEFAULT_DATABASE
from scripts.check_stage2_preflight import snapshot
from scripts.check_stage1b_acceptance import vector_fingerprint

TOOL = ROOT.parent / "layoutpatch/artifacts/route_v2_external/preparation_v1/mineru_tool_v1"


def digest(path):
    if os.name == "nt" and len(str(path)) >= 240 and not str(path).startswith("\\\\?\\"):
        path = type(path)("\\\\?\\" + str(path.resolve()))
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    output = ROOT / "runtime/verification/r20"
    output.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(DEFAULT_DATABASE)) as source, closing(sqlite3.connect(output / "metadata-before.sqlite3")) as target:
        source.backup(target)
        collection = source.execute("SELECT collection_name FROM index_generations WHERE id=(SELECT active_index_id FROM system_state WHERE id=1)").fetchone()[0]
    folders = ("backend", "scripts", "tests", "migrations", "frontend/app", "frontend/lib", "frontend/tests", "configs", "docs")
    files = [p for f in folders for p in (ROOT / f).rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".cjs", ".json", ".md", ".css") and "__pycache__" not in p.parts]
    files += [ROOT / n for n in ("AGENTS.md", ".gitignore", "requirements-colpali.in", "requirements-colpali.lock.txt", "requirements-web.in", "requirements-web.lock.txt", "frontend/package.json", "frontend/yarn.lock")]
    model_root = TOOL / "mineru_home/models/MinerU-4_models_onnx"
    models = {p.relative_to(model_root).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in model_root.rglob("*") if p.is_file()}
    site = TOOL / ".venv/Lib/site-packages"
    packages = sorted((d.metadata["Name"], d.version) for d in metadata.distributions(path=[str(site)]))
    parser_files = {p.relative_to(site).as_posix(): digest(p) for package in ("mineru", "docvortex") for p in (site / package).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    ps = "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object LocalPort -In 3000,8000,8001,6333 | Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"
    ports = json.loads(subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True))
    report = {"date": "2026-11-08", "round": "R20", "stage": "2-4", "database": snapshot(DEFAULT_DATABASE),
              "collection": collection, "qdrant": vector_fingerprint(collection), "ports": ports,
              "git_status": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True),
              "files": {p.relative_to(ROOT).as_posix(): digest(p) for p in files if p.is_file()},
              "parser_source": str(TOOL), "parser_packages": packages, "parser_source_files": parser_files,
              "models": models, "web_packages": sorted((d.metadata["Name"], d.version) for d in metadata.distributions()),
              "visible_same_project_windows": "current active; other two notLoaded at initial read"}
    target = ROOT / "docs/checks/stage2-4-preflight.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"revision": report["database"]["revision"], "tables": {k: v["count"] for k,v in report["database"]["tables"].items()}, "onnx_count": len([k for k in models if k.endswith(".onnx")]), "onnx_bytes": sum(v["bytes"] for k,v in models.items() if k.endswith(".onnx")), "baseline": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
