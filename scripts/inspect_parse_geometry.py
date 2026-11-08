"""Re-render one source page with the frozen renderer and verify the exact stored PNG identity."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def inspect(request):
    import pymupdf as fitz
    source = Path(request["pdf_path"]).resolve(strict=True)
    if not source.is_relative_to((ROOT / "runtime").resolve()):
        raise ValueError("Invalid private PDF")
    data = source.read_bytes()
    if len(data) > 20*1024*1024 or hashlib.sha256(data).hexdigest() != request["pdf_sha256"]:
        raise ValueError("PDF identity mismatch")
    with fitz.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass or len(pdf) != request["page_count"]:
            raise ValueError("PDF identity mismatch")
        page = pdf[request["identity"]["page_index"]]
        rect = page.rect
        if rect.width*2 > 10000 or rect.height*2 > 10000 or rect.width*rect.height*4 > 40000000:
            raise ValueError("Excessive render geometry")
        pix = page.get_pixmap(dpi=144, colorspace=fitz.csRGB, alpha=False)
        digest = hashlib.sha256(pix.tobytes("png")).hexdigest()
        identity = request["identity"]
        if (pix.width, pix.height, digest) != (identity["width_px"],identity["height_px"],identity["render_sha256"]):
            raise ValueError("Stored PNG and source renderer disagree")
        return {"renderer": "PyMuPDF", "renderer_version": fitz.VersionBind, "dpi": 144,
                "width_px": pix.width, "height_px": pix.height, "render_sha256": digest,
                "rotation": page.rotation, "mediabox": list(page.mediabox), "cropbox": list(page.cropbox),
                "page_rect": list(rect), "page_size_points": [rect.width,rect.height],
                "pdf_transformation_matrix": list(page.transformation_matrix), "pdf_rotation_matrix": list(page.rotation_matrix),
                "pixmap_origin": [pix.x,pix.y], "parser_points_to_png": [2,0,0,2,-pix.x,-pix.y]}


if __name__ == "__main__":
    path = Path(sys.argv[1]).resolve(strict=True)
    if not path.is_relative_to((ROOT / "runtime/parsing").resolve()):
        raise SystemExit(1)
    with (path.parent / "geometry.json").open("x", encoding="utf-8") as stream:
        json.dump(inspect(json.loads(path.read_text(encoding="utf-8"))), stream, allow_nan=False, indent=2)
