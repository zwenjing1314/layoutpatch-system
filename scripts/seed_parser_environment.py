"""Copy the already installed CPU parser environment locally, with RECORD checks; no pip/network."""
import base64
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from scripts.check_parsing_preflight import TOOL, digest
from backend.db.connection import ROOT


def main():
    destination = ROOT / ".venv-parser"
    if not destination.exists():
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(destination)], check=True)
    source, target = TOOL / ".venv/Lib/site-packages", destination / "Lib/site-packages"
    distributions = sorted(metadata.distributions(path=[str(source)]), key=lambda d: d.metadata["Name"].lower())
    report = {"source": str(source), "destination": str(target), "method": "independent RECORD-verified file copies, no .pth/launchers/source sys.path", "downloaded": False, "files": {}, "packages": {}}
    for dist in distributions:
        if dist.read_text("direct_url.json") and '"editable": true' in dist.read_text("direct_url.json"):
            raise ValueError("Editable parser distribution refused")
        report["packages"][dist.metadata["Name"]] = dist.version
        for item in dist.files or []:
            relative = Path(str(item))
            src = (source / relative).resolve()
            if not src.is_relative_to(source.resolve()) or "__pycache__" in relative.parts or relative.suffix in (".pyc", ".pth"):
                continue
            dst = (target / relative).resolve()
            if not dst.is_relative_to(target.resolve()):
                raise ValueError("Parser file escapes destination")
            sha = digest(src)
            if item.hash and item.hash.mode == "sha256" and base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip("=") != item.hash.value:
                raise ValueError("Parser source RECORD mismatch: " + str(relative))
            if dst.exists() and digest(dst) != sha:
                raise ValueError("Existing parser environment differs: " + str(relative))
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile("\\\\?\\" + str(src) if os.name == "nt" else src, "\\\\?\\" + str(dst) if os.name == "nt" else dst)
            if digest(dst) != sha:
                raise ValueError("Parser copy verification failed")
            report["files"][relative.as_posix()] = sha
    lock = "# Local CPU parser copy; exact installed snapshot, no download.\n" + "\n".join(f"{k}=={v}" for k,v in sorted(report["packages"].items(), key=lambda p:p[0].lower())) + "\n"
    lock_path = ROOT / "requirements-parser.lock.txt"
    if lock_path.exists() and lock_path.read_text(encoding="utf-8") != lock:
        raise ValueError("Parser lock differs; refusing overwrite")
    lock_path.write_text(lock, encoding="utf-8")
    receipt = ROOT / "runtime/checks/parser-environment-seed.json"
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    baseline = json.loads((ROOT / "docs/checks/stage2-4-preflight.json").read_text(encoding="utf-8"))
    config = {"schema": "mineru-parser-profile-v1", "name": "mineru_4_0_10_basic_onnx_cpu_v1", "python": ".venv-parser/Scripts/python.exe",
              "model_root": "../layoutpatch/artifacts/route_v2_external/preparation_v1/mineru_tool_v1/mineru_home/models/MinerU-4_models_onnx",
              "source_repository": "opendatalab/MinerU-4_models_onnx", "source_revision": "358310b4f64b95f9fefc372ad899356e4111f376",
              "model_files": {k:v for k,v in baseline["models"].items() if not k.startswith(".cache/")},
              "package_lock_sha256": digest(lock_path), "environment_receipt": receipt.relative_to(ROOT).as_posix(), "environment_receipt_sha256": digest(receipt),
              "mineru": "4.0.10", "docvortex": "0.5.10", "onnxruntime": "1.30.0", "tier": "basic", "ocr_mode": "auto", "provider": "CPUExecutionProvider",
              "candidate_policy": "all_top_level_blocks_no_query_no_gold", "coordinate_adapter": "docvortex2-to-pymupdf144-v1", "geometry_policy": "rotation0_origin0_crop_equals_media_only", "page_timeout_seconds": 180, "max_output_bytes": 33554432}
    config_path = ROOT / "configs/mineru_local.json"
    encoded = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if config_path.exists() and config_path.read_text(encoding="utf-8") != encoded:
        raise ValueError("Frozen parser config differs")
    config_path.write_text(encoded, encoding="utf-8")
    print(f"Copied and verified {len(report['packages'])} parser packages / {len(report['files'])} files; no downloads")


if __name__ == "__main__":
    main()
