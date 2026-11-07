"""Bounded private subprocess renderer using the existing frozen PyMuPDF environment."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def render(input_path, output, expected_sha256, expected_pages):
    import pymupdf
    source, output = Path(input_path).resolve(strict=True), Path(output).resolve()
    if (not source.is_relative_to((ROOT / "runtime").resolve())
            or not output.is_relative_to((ROOT / "runtime/corpus/ingest").resolve())):
        raise ValueError("Invalid private input/output")
    data = source.read_bytes()
    if len(data) > 20 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("PDF identity mismatch")
    profile = {"schema": "uploaded-pdf-render-v1", "renderer": "PyMuPDF", "version": pymupdf.VersionBind,
               "dpi": 144, "colorspace": "RGB", "format": "PNG", "alpha": False,
               "geometry": "PyMuPDF page crop and rotation applied"}
    pages = []
    output.mkdir(parents=True, exist_ok=False)
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass or len(pdf) != expected_pages or not 0 < len(pdf) <= 1000:
            raise ValueError("Invalid PDF page identity")
        for number, page in enumerate(pdf):
            width, height = page.rect.width * 2, page.rect.height * 2
            if not all(math.isfinite(v) and 0 < v <= 10000 for v in (width, height)) or width * height > 40000000:
                raise ValueError("Page geometry exceeds renderer limit")
            image = page.get_pixmap(dpi=144, colorspace=pymupdf.csRGB, alpha=False)
            path = output / f"page-{number:04}.png"
            image.save(path)
            encoded = path.read_bytes()
            if len(encoded) > 20 * 1024 * 1024:
                raise ValueError("PNG exceeds preview limit")
            pages.append({"page_index": number, "image_path": path.relative_to(ROOT).as_posix(),
                          "width_px": image.width, "height_px": image.height,
                          "render_sha256": hashlib.sha256(encoded).hexdigest(),
                          "pdf_rotation": page.rotation, "pdf_mediabox": list(page.mediabox), "pdf_cropbox": list(page.cropbox)})
    result = {"pdf_sha256": expected_sha256, "render_profile": profile, "pages": pages}
    (output / "render-manifest.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    try:
        render(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]))
        print('{"status":"ok"}')
    except Exception:
        print('{"status":"failed"}')
        raise SystemExit(1)
