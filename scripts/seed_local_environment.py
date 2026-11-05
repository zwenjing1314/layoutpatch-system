"""Materialize a local, independent Windows environment without downloading wheels.

Run using a bootstrap Python with packaging installed. Create the destination venv
with Python 3.11 first. Copy only the locked distributions' recorded site-package
files, never old project code, editable hooks, launchers or Python executables.
This is a local bootstrap, not a distributable wheel builder. Console launchers
are intentionally omitted; use python -m for commands.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-site", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_site.resolve(strict=True)
    target = ROOT / ".venv/Lib/site-packages"
    executable = ROOT / ".venv/Scripts/python.exe"
    info = json.loads(subprocess.check_output([
        str(executable), "-c",
        "import sys,json; print(json.dumps({'version':sys.version.split()[0],"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix}))",
    ], text=True))
    if not info["version"].startswith("3.11.") or Path(info["prefix"]).resolve() != ROOT / ".venv":
        raise ValueError("Destination must be this project's independent Python 3.11 venv")
    if source == target.resolve() or not target.is_dir():
        raise ValueError("Invalid source or missing destination")
    distributions = {canonicalize_name(d.metadata["Name"]): d
                     for d in metadata.distributions(path=[str(source)])}
    pending = [Requirement(line) for line in (ROOT / "requirements-colpali.in").read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    env = default_environment()
    env.update(python_version="3.11", python_full_version=info["version"], extra="")
    selected = {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        dist = distributions[name]
        if dist.version not in requirement.specifier:
            raise ValueError(f"Source dependency does not satisfy {requirement}: {dist.version}")
        if name in selected:
            continue
        if dist.read_text("direct_url.json") and '"editable": true' in dist.read_text("direct_url.json"):
            raise ValueError(f"Editable distribution forbidden: {name}")
        selected[name] = dist
        for spec in dist.requires or []:
            dependency = Requirement(spec)
            if dependency.marker is None or dependency.marker.evaluate(env):
                pending.append(dependency)
    lock = "\n".join(f"{name}=={dist.version}" for name, dist in sorted(selected.items())) + "\n"
    lock_path = ROOT / "requirements-colpali.lock.txt"
    if lock_path.exists() and lock_path.read_text("utf-8") != lock:
        raise ValueError("Existing lock disagrees with source environment; refusing to overwrite")
    report = {"schema": "local-environment-seed-v1", "source_site": str(source),
              "destination": str(target), "python": info, "downloaded": False,
              "method": "independent file copies; no source sys.path; no console launchers",
              "packages": {}, "files": [], "skipped": []}
    for name, dist in sorted(selected.items()):
        count = 0
        for item in dist.files or []:
            relative = Path(str(item))
            src = (source / relative).resolve()
            if not src.is_relative_to(source) or "__pycache__" in relative.parts or relative.suffix == ".pyc":
                report["skipped"].append(str(item))
                continue
            dst = target / relative
            if not dst.resolve().is_relative_to(target.resolve()):
                raise ValueError(f"Path escapes destination: {item}")
            sha = digest(src)
            if item.hash and item.hash.mode == "sha256":
                encoded = base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip("=")
                if encoded != item.hash.value:
                    raise ValueError(f"Installed file differs from distribution RECORD: {src}")
            if dst.exists() and digest(dst) != sha:
                raise ValueError(f"Destination already has different bytes: {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile(src, dst)
            if digest(dst) != sha:
                raise ValueError(f"Copied file hash mismatch: {dst}")
            report["files"].append({"package": name, "path": str(relative), "sha256": sha})
            count += 1
        report["packages"][name] = {"version": dist.version, "copied_files": count}
        print(f"{name}=={dist.version}: {count} files verified", flush=True)
    lock_path.write_text(lock, encoding="utf-8")
    output = ROOT / "runtime/checks/environment-seed.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Verified {len(selected)} distributions; report: {output}", flush=True)


if __name__ == "__main__":
    main()
