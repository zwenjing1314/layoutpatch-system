"""Select two complete, small PDFs by filename/page count, never by gold pages."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/corpus")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "runtime") or output.exists():
        raise ValueError("Use a new output directory below this project's runtime/")
    output.mkdir(parents=True)
    manifest = {"schema": "complete-pdf-development-corpus-v1", "development_only": True,
                "source_archive": str(args.archive.resolve()),
                "selection": "first two PDFs sorted by archive filename with 2..8 pages",
                "annotation_or_gold_used": False, "dpi": 144, "documents": [], "pages": [], "scanned": []}
    with args.archive.open("rb") as stream:
        manifest["source_archive_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    with tarfile.open(args.archive) as archive:
        members = sorted((m for m in archive if m.isfile() and m.name.lower().endswith(".pdf")),
                         key=lambda m: m.name)
        for member in members:
            data = archive.extractfile(member).read()
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                manifest["scanned"].append({"member": member.name, "page_count": len(pdf)})
                if not 2 <= len(pdf) <= 8:
                    continue
                doc_id = sha256(data)[:16]
                doc_dir = output / doc_id
                doc_dir.mkdir()
                # Do not extract archive paths: assign a server-generated local name.
                (doc_dir / "source.pdf").write_bytes(data)
                manifest["documents"].append({"document_id": doc_id, "archive_member": member.name,
                    "pdf_path": str((doc_dir / "source.pdf").relative_to(output)),
                    "sha256": sha256(data), "page_count": len(pdf)})
                for index, page in enumerate(pdf):
                    if page.rotation != 0 or page.cropbox != page.mediabox:
                        raise ValueError("Development rendering expects no rotation or cropped page")
                    image = page.get_pixmap(dpi=144, colorspace=pymupdf.csRGB, alpha=False)
                    image_path = doc_dir / f"page-{index + 1:03}.png"
                    image.save(image_path)
                    # Reading aid only, never used by the visual retrieval encoder.
                    (doc_dir / f"page-{index + 1:03}.txt").write_text(page.get_text(), encoding="utf-8")
                    manifest["pages"].append({"document_id": doc_id, "page_id": f"{doc_id}:p{index}",
                        "page_index": index, "page_number": index + 1,
                        "image_path": str(image_path.relative_to(output)),
                        "image_sha256": sha256(image_path.read_bytes()),
                        "width": image.width, "height": image.height})
                if len(manifest["documents"]) == 2:
                    break
    if len(manifest["documents"]) != 2:
        raise ValueError("Archive does not contain two eligible complete PDFs")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    sheet = Image.new("RGB", (1000, 330 * ((len(manifest["pages"]) + 4) // 5)), "#e8e8e8")
    draw = ImageDraw.Draw(sheet)
    for i, page in enumerate(manifest["pages"]):
        with Image.open(output / page["image_path"]) as image:
            image.thumbnail((190, 295))
            x, y = (i % 5) * 200, (i // 5) * 330
            sheet.paste(image, (x + (200 - image.width) // 2, y + 25))
            draw.text((x + 5, y + 5), f"{page['document_id'][:6]} / p{page['page_number']}", fill="black")
    sheet.save(output / "contact-sheet.png")
    print(json.dumps({"documents": len(manifest["documents"]), "pages": len(manifest["pages"]),
                      "manifest": str(output / "manifest.json")}))


if __name__ == "__main__":
    main()
