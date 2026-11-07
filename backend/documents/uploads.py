"""PDF input validation and private durable storage; no rendering or model calls."""
from dataclasses import dataclass
from io import BytesIO
import math
import os
from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader

from backend.db.connection import ROOT


@dataclass(frozen=True)
class UploadSettings:
    root: Path = ROOT / "runtime/uploads"
    max_bytes: int = 20 * 1024 * 1024
    max_pages: int = 100

    def __post_init__(self):
        if not self.root.resolve().is_relative_to((ROOT / "runtime").resolve()):
            raise ValueError("Upload storage must be inside project runtime")
        if not 0 < self.max_bytes <= 20 * 1024 * 1024 or not 0 < self.max_pages <= 1000:
            raise ValueError("Invalid upload limits")

    @classmethod
    def from_environment(cls):
        return cls(root=Path(os.getenv("LAYOUTPATCH_UPLOAD_ROOT", str(ROOT / "runtime/uploads"))),
                   max_bytes=int(os.getenv("LAYOUTPATCH_UPLOAD_MAX_BYTES", str(20 * 1024 * 1024))),
                   max_pages=int(os.getenv("LAYOUTPATCH_UPLOAD_MAX_PAGES", "100")))


def validate_pdf(data, name, content_type, settings):
    if (not name or len(name) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or any(c in name for c in '/\\:') or not name.lower().endswith(".pdf")):
        raise HTTPException(422, "INVALID_FILENAME")
    if content_type != "application/pdf":
        raise HTTPException(415, "PDF_REQUIRED")
    if len(data) > settings.max_bytes:
        raise HTTPException(413, "PDF_TOO_LARGE")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "INVALID_PDF")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise HTTPException(422, "ENCRYPTED_PDF")
        count = len(reader.pages)
        if count > settings.max_pages:
            raise HTTPException(413, "PDF_TOO_MANY_PAGES")
        if count < 1:
            raise ValueError()
        for page in reader.pages:
            if any(not math.isfinite(v) or v <= 0 for v in (float(page.mediabox.width), float(page.mediabox.height))):
                raise ValueError()
        return count
    except HTTPException:
        raise
    except Exception:
        # Parser diagnostics never become public filesystem/input details.
        raise HTTPException(422, "INVALID_PDF") from None


def write_pdf(path, data):
    path.parent.mkdir(parents=True, exist_ok=False)
    temporary = path.with_suffix(".part")
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def cleanup_pdf(path):
    # Only server-generated names; failures remain diagnosable by the job.
    for candidate in (path.with_suffix(".part"), path):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        path.parent.rmdir()
    except OSError:
        pass
