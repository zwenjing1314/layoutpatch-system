"""Validate complete local corpus, then insert missing metadata in one transaction."""
import hashlib
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .connection import ROOT
from .models import Document, DocumentVersion, IndexGeneration, Page, PipelineProfile, User

OWNERSHIP = ROOT / "configs/development_ownership.json"
MANIFEST = ROOT / "runtime/corpus/manifest.json"
password_hasher = PasswordHash.recommended()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


def local_file(base: Path, value: str):
    if not isinstance(value, str) or not value:
        raise ValueError("Missing corpus path")
    path = (base / value.replace("\\", "/")).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("Corpus path missing or outside corpus directory")
    return path


def validate_corpus(manifest_path: Path = MANIFEST):
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_relative_to((ROOT / "runtime").resolve()):
        raise ValueError("Manifest must be inside this project's runtime/")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ownership = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
    if data["schema"] != "complete-pdf-development-corpus-v1" or data["dpi"] != 144:
        raise ValueError("Unexpected development render identity")
    if data.get("development_only") is not True:
        raise ValueError("Expected development corpus")
    docs = data["documents"]
    if len(docs) != len(ownership["documents"]) or {d["document_id"] for d in docs} != set(ownership["documents"]):
        raise ValueError("Unexpected or duplicate corpus document")
    page_ids = [p["page_id"] for p in data["pages"]]
    if len(page_ids) != len(set(page_ids)) or any(p["document_id"] not in ownership["documents"] for p in data["pages"]):
        raise ValueError("Duplicate or orphan corpus page")
    result = []
    for doc in docs:
        expected = ownership["documents"][doc["document_id"]]
        pdf = local_file(manifest_path.parent, doc["pdf_path"])
        if doc["sha256"] != expected["sha256"] or sha(pdf.read_bytes()) != expected["sha256"]:
            raise ValueError("PDF hash mismatch")
        count = expected["page_count"]
        reader = PdfReader(pdf)
        if reader.is_encrypted or len(reader.pages) != count or doc["page_count"] != count:
            raise ValueError("Complete PDF page count mismatch")
        pages = sorted((p for p in data["pages"] if p["document_id"] == doc["document_id"]), key=lambda p: p["page_index"])
        if [p["page_index"] for p in pages] != list(range(count)):
            raise ValueError("Missing, duplicate or non-contiguous page sequence")
        checked_pages = []
        for page in pages:
            if page["page_number"] != page["page_index"] + 1 or page["page_id"] != f"{doc['document_id']}:p{page['page_index']}":
                raise ValueError("Page identity mismatch")
            image_path = local_file(manifest_path.parent, page["image_path"])
            if sha(image_path.read_bytes()) != page["image_sha256"]:
                raise ValueError("Page image hash mismatch")
            with Image.open(image_path) as image:
                if image.size != (page["width"], page["height"]) or image.format != "PNG" or image.mode != "RGB":
                    raise ValueError("Page image geometry/format mismatch")
                image.verify()
            checked_pages.append({"source_page_id": page["page_id"], "page_index": page["page_index"],
                                  "width_px": page["width"], "height_px": page["height"],
                                  "render_sha256": page["image_sha256"],
                                  "image_path": image_path.relative_to(ROOT).as_posix()})
        result.append({"source_key": "development:" + doc["document_id"], "owner": expected["owner"],
                       "display_name": expected["display_name"], "pdf_sha256": expected["sha256"],
                       "pdf_path": pdf.relative_to(ROOT).as_posix(), "page_count": count, "pages": checked_pages})
    return result


def match(row, expected):
    if any(getattr(row, key) != value for key, value in expected.items()):
        raise ValueError("Existing metadata conflicts with seed identity; no overwrite performed")


def require_revision(connection):
    if connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() not in ("0003_search_pages", "0004_upload_jobs", "0005_ingestion", "0006_document_names", "0007_job_attempts"):
        raise ValueError("Run the database migration first")


def seed(engine, password_provider, manifest_path: Path = MANIFEST):
    # Expensive file verification happens before the write lock; no GPU or network.
    documents = validate_corpus(manifest_path)
    ownership = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
    render_json = canonical({"schema": "complete-pdf-development-corpus-v1", "dpi": 144, "colorspace": "RGB", "format": "PNG"})
    config = {"encoder": json.loads((ROOT / "configs/colpali_local.json").read_text(encoding="utf-8")),
              "render": json.loads(render_json),
              "qdrant_design": {"vector_name": "original", "dimension": 128, "distance": "Dot", "multivector": "MAX_SIM", "exact": True}}
    config_json = canonical(config)
    created = dict(users=0, documents=0, versions=0, pages=0, profiles=0, indexes=0)
    with engine.connect() as connection:
        require_revision(connection)
        connection.commit()
        # Serialize concurrent initializers, not just a check followed by unsafe inserts.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection, expire_on_commit=False) as session:
                users = {}
                for username, role in ownership["users"].items():
                    user = session.scalar(select(User).where(User.username == username))
                    if user is None:
                        password = password_provider(username)
                        if not isinstance(password, str) or len(password) < 12:
                            raise ValueError("Initial password must contain at least 12 characters")
                        user = User(username=username, role=role, password_hash=password_hasher.hash(password))
                        session.add(user)
                        session.flush()
                        created["users"] += 1
                    else:
                        match(user, {"username": username, "role": role})
                    users[username] = user
                for item in documents:
                    doc = session.scalar(select(Document).where(Document.source_key == item["source_key"]))
                    new_document = doc is None
                    identity = {"owner_id": users[item["owner"]].id, "visibility": "private"}
                    if doc is None:
                        doc = Document(source_key=item["source_key"], display_name=item["display_name"], **identity)
                        session.add(doc)
                        session.flush()
                        created["documents"] += 1
                    else:
                        match(doc, identity)
                    expected = {key: item[key] for key in ("pdf_sha256", "pdf_path", "page_count")}
                    expected.update(render_profile_json=render_json, render_profile_sha256=sha(render_json.encode()))
                    version = session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.version == 1))
                    if version is None:
                        version = DocumentVersion(document_id=doc.id, version=1, **expected)
                        session.add(version)
                        session.flush()
                        created["versions"] += 1
                    else:
                        match(version, expected)
                    # Never restore or change an existing active version on a repeat run.
                    if new_document:
                        doc.active_version_id = version.id
                    for expected_page in item["pages"]:
                        page = session.scalar(select(Page).where(Page.source_page_id == expected_page["source_page_id"]))
                        values = {"document_version_id": version.id, **expected_page}
                        if page is None:
                            session.add(Page(**values))
                            created["pages"] += 1
                        else:
                            match(page, values)
                    session.flush()
                    if len(session.scalars(select(Page).where(Page.document_version_id == version.id)).all()) != item["page_count"]:
                        raise ValueError("Database has extra/missing pages for seed version")
                profile = session.scalar(select(PipelineProfile).where(PipelineProfile.name == "colpali_full_v1"))
                expected_profile = {"config_json": config_json, "config_sha256": sha(config_json.encode())}
                if profile is None:
                    profile = PipelineProfile(name="colpali_full_v1", **expected_profile)
                    session.add(profile)
                    session.flush()
                    created["profiles"] += 1
                else:
                    match(profile, expected_profile)
                collection_name = "layoutpatch_system_original_" + profile.config_sha256[:16] + "_g1"
                index = session.scalar(select(IndexGeneration).where(IndexGeneration.collection_name == collection_name))
                if index is None:
                    session.add(IndexGeneration(profile_id=profile.id, collection_name=collection_name))
                    created["indexes"] += 1
                else:
                    match(index, {"profile_id": profile.id})
                session.flush()
                session.commit()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return created
