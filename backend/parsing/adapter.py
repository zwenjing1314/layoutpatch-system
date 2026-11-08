"""Trusted local resources and bounded subprocesses. No parser imports in Web."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from backend.db.connection import ROOT
from backend.db.seed import canonical, sha
from .candidates import ParseError, export_candidates

CONFIG = ROOT / "configs/mineru_local.json"
IDENTITY_FILES = ("backend/parsing/candidates.py", "backend/parsing/adapter.py", "scripts/mineru_page_worker.py", "scripts/inspect_parse_geometry.py")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def load_profile():
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        if (value["schema"] != "mineru-parser-profile-v1" or value["tier"] != "basic" or value["provider"] != "CPUExecutionProvider"
                or value["ocr_mode"] != "auto" or value["geometry_policy"] != "rotation0_origin0_crop_equals_media_only"
                or not 1 <= value["page_timeout_seconds"] <= 600):
            raise ValueError()
        value["implementation_sha256"] = {name: digest(ROOT / name) for name in IDENTITY_FILES}
        return value
    except (OSError, ValueError, KeyError):
        raise ParseError("PARSER_RESOURCES_UNAVAILABLE") from None


def verify_resources(profile):
    try:
        if profile != load_profile() or digest(ROOT / "requirements-parser.lock.txt") != profile["package_lock_sha256"]:
            raise ValueError()
        python = (ROOT / profile["python"]).resolve(strict=True)
        if python != (ROOT / ".venv-parser/Scripts/python.exe").resolve():
            raise ValueError()
        receipt_path = (ROOT / profile["environment_receipt"]).resolve(strict=True)
        if not receipt_path.is_relative_to((ROOT / "runtime/checks").resolve()) or digest(receipt_path) != profile["environment_receipt_sha256"]:
            raise ValueError()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        site = ROOT / ".venv-parser/Lib/site-packages"
        for relative, expected in receipt["files"].items():
            path = (site / relative).resolve(strict=True)
            if not path.is_relative_to(site.resolve()) or digest(path) != expected:
                raise ValueError()
        model_root = (ROOT / profile["model_root"]).resolve(strict=True)
        for relative, expected in profile["model_files"].items():
            path = (model_root / relative).resolve(strict=True)
            if not path.is_relative_to(model_root) or path.stat().st_size != expected["bytes"] or digest(path) != expected["sha256"]:
                raise ValueError()
    except (OSError,ValueError,KeyError):
        raise ParseError("PARSER_RESOURCE_IDENTITY_MISMATCH") from None


def run_child(python, script, request_path, timeout, log_name):
    # No inherited auth/app/model credentials, user MinerU configuration or proxy.
    env = {k:v for k,v in os.environ.items() if k.upper() in {"SYSTEMROOT","WINDIR","COMSPEC","PATH","PATHEXT","SYSTEMDRIVE"}}
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    with (request_path.parent / log_name).open("xb") as log:
        try:
            result = subprocess.run([str(python),"-B",str(ROOT / script),str(request_path)], cwd=request_path.parent, env=env,
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except subprocess.TimeoutExpired:
            raise ParseError("PARSER_TIMEOUT") from None
    if result.returncode:
        raise ParseError("PARSER_EXECUTION_FAILED" if "mineru" in script else "RENDER_IDENTITY_MISMATCH")


def parse_page(task_id, version, page, profile):
    if profile != load_profile():
        raise ParseError("PARSER_PROFILE_CHANGED")
    output = ROOT / "runtime/parsing" / task_id / page.id
    output.mkdir(parents=True, exist_ok=False)
    identity = {"document_id": version.document_id, "document_version_id": version.id, "page_id": page.id,
                "page_index": page.page_index, "page_number": page.page_index+1, "width_px": page.width_px,
                "height_px": page.height_px, "render_sha256": page.render_sha256, "parser_profile_sha256": sha(canonical(profile).encode())}
    source = (ROOT / version.pdf_path).resolve(strict=True)
    if not source.is_relative_to((ROOT / "runtime").resolve()):
        raise ParseError("PARSER_INPUT_INVALID")
    request_path = output / "request.json"
    request_path.write_text(canonical({"profile": profile, "identity": identity, "pdf_path": str(source), "pdf_sha256": version.pdf_sha256, "page_count": version.page_count}), encoding="utf-8")
    run_child(ROOT / ".venv/Scripts/python.exe", "scripts/inspect_parse_geometry.py", request_path, 180, "geometry.log")
    geometry = json.loads((output / "geometry.json").read_text(encoding="utf-8"))
    if geometry["rotation"] != 0 or geometry["cropbox"] != geometry["mediabox"] or geometry["mediabox"][:2] != [0,0]:
        raise ParseError("UNSUPPORTED_PDF_GEOMETRY")
    run_child(ROOT / profile["python"], "scripts/mineru_page_worker.py", request_path, profile["page_timeout_seconds"], "parser.log")
    receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    raw_path = output / "raw.json"
    if (receipt["status"] != "completed" or receipt["network_attempts"] or receipt["blocked_writes"]
            or raw_path.stat().st_size > profile["max_output_bytes"] or digest(raw_path) != receipt["raw_sha256"]
            or not receipt["sessions"] or sum(s["forward_calls"] for s in receipt["sessions"]) == 0
            or any(s["providers"] != ["CPUExecutionProvider"] for s in receipt["sessions"])):
        raise ParseError("PARSER_RECEIPT_INVALID")
    candidates = export_candidates(json.loads(raw_path.read_text(encoding="utf-8")), identity, geometry)
    if profile != load_profile():
        raise ParseError("PARSER_PROFILE_CHANGED")
    provenance = {"geometry": geometry, "raw_path": raw_path.relative_to(ROOT).as_posix(), "raw_sha256": receipt["raw_sha256"],
                  "receipt_path": (output / "receipt.json").relative_to(ROOT).as_posix(), "receipt_sha256": digest(output / "receipt.json"),
                  "parser_versions": receipt["packages"], "profile_sha256": identity["parser_profile_sha256"], "pdf_sha256": version.pdf_sha256}
    return candidates, provenance
