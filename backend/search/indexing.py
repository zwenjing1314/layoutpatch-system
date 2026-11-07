"""Explicit verified development import; no overwrite of an unknown or partial index."""
import hashlib
import json
from pathlib import Path
import struct

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Page, PipelineProfile
from backend.db.seed import canonical, match, sha, validate_corpus
from .qdrant import Qdrant, SearchUnavailable, validate_vector


def feature_digest(vector):
    return hashlib.sha256(b"".join(struct.pack("<128f", *row) for row in vector)).hexdigest()


def read_bundle(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / "runtime"):
        raise ValueError("Feature bundle must be inside project runtime")
    data = json.loads(path.read_text(encoding="utf-8"))
    source = json.loads((ROOT / "configs/development_features.json").read_text())
    if data["schema"] != "verified-search-features-v1" or data["source"] != source:
        raise ValueError("Feature bundle identity mismatch")
    for name, expected in source["files"].items():
        if sha((ROOT / source["source_directory"] / name).read_bytes()) != expected:
            raise ValueError("Original feature evidence changed")
    if sha((ROOT / "configs/colpali_local.json").read_bytes()) != source["encoder_profile_sha256"] or sha((ROOT / "runtime/corpus/manifest.json").read_bytes()) != source["corpus_manifest_sha256"]:
        raise ValueError("Corpus/encoder changed")
    pages = {}
    for entry in data["pages"]:
        file = (path.parent / entry["file"]).resolve()
        if not file.is_relative_to(path.parent) or sha(file.read_bytes()) != entry["json_sha256"]:
            raise ValueError("Export file mismatch")
        vector = validate_vector(json.loads(file.read_text()), rows=1031)
        if entry["source_page_id"] in pages or entry["token_count"] != 1031 or feature_digest(vector) != entry["embedding_sha256"]:
            raise ValueError("Export tensor mismatch")
        pages[entry["source_page_id"]] = (entry, vector)
    return data, pages


def import_features(engine, bundle_path, qdrant=None):
    qdrant = qdrant or Qdrant()
    bundle, features = read_bundle(bundle_path)
    corpus = validate_corpus()
    expected_pages = {p["source_page_id"] for doc in corpus for p in doc["pages"]}
    if set(features) != expected_pages:
        raise ValueError("Missing/extra complete-corpus features")
    # A bounded local import holds the writer lock through verification and final
    # activation. Remote partial writes after a failure stay unusable (DB rollback).
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with Session(bind=connection, expire_on_commit=False) as db:
                profile = db.scalar(select(PipelineProfile).where(PipelineProfile.name == "colpali_full_v1"))
                if profile is None or sha(profile.config_json.encode()) != profile.config_sha256:
                    raise ValueError("Missing or changed profile")
                config = json.loads(profile.config_json)
                if config["encoder"] != json.loads((ROOT / "configs/colpali_local.json").read_text()):
                    raise ValueError("Encoder profile mismatch")
                indexes = db.scalars(select(IndexGeneration).where(IndexGeneration.profile_id == profile.id)).all()
                if len(indexes) != 1:
                    raise ValueError("Expected one development index")
                index = indexes[0]
                if index.status not in ("pending", "ready"):
                    raise ValueError("Index is not importable")
                points, documents = [], []
                for expected_doc in corpus:
                    doc = db.scalar(select(Document).where(Document.source_key == expected_doc["source_key"]))
                    if doc is None or doc.status not in ("registered", "ready") or doc.deleted_at is not None:
                        raise ValueError("Invalid document state")
                    version = db.get(DocumentVersion, doc.active_version_id)
                    if version is None or version.document_id != doc.id:
                        raise ValueError("Invalid active version")
                    match(version, {k: expected_doc[k] for k in ("pdf_sha256", "pdf_path", "page_count")})
                    if json.loads(version.render_profile_json) != config["render"] or sha(version.render_profile_json.encode()) != version.render_profile_sha256:
                        raise ValueError("Render profile mismatch")
                    actual_pages = db.scalars(select(Page).where(Page.document_version_id == version.id).order_by(Page.page_index)).all()
                    if len(actual_pages) != len(expected_doc["pages"]):
                        raise ValueError("Page count mismatch")
                    documents.append(doc)
                    for page, expected_page in zip(actual_pages, expected_doc["pages"], strict=True):
                        match(page, expected_page)
                        entry, vector = features[page.source_page_id]
                        if page.render_sha256 != entry["render_sha256"]:
                            raise ValueError("Rendered feature mismatch")
                        points.append({"id": page.id, "vector": {"original": vector}, "payload": {
                            "page_id": page.id, "document_id": doc.id, "document_version_id": version.id,
                            "profile_id": profile.id, "index_generation": index.id,
                            "owner_id": doc.owner_id, "visibility": doc.visibility,
                            "render_sha256": page.render_sha256, "embedding_sha256": entry["embedding_sha256"]}})
                info = qdrant.info(index.collection_name)
                existing = info is not None
                if existing:
                    qdrant.check_info(info, len(points))
                else:
                    if index.status == "ready":
                        raise SearchUnavailable("Active collection missing; no automatic recreation")
                    qdrant.create(index.collection_name)
                    for point in points:
                        qdrant.upsert(index.collection_name, [point])
                qdrant.check_info(qdrant.info(index.collection_name), len(points))
                actual = qdrant.all_points(index.collection_name)
                lookup = {str(p["id"]): p for p in actual}
                if len(actual) != len(points) or len(lookup) != len(points):
                    raise SearchUnavailable("Remote membership mismatch")
                for point in points:
                    remote = lookup.get(point["id"])
                    # Qdrant JSON prints f32 values with shortest f32 precision;
                    # Python JSON parses f64. Compare the actual float32 bytes.
                    if (remote is None or remote["payload"] != point["payload"]
                        or set(remote["vector"]) != {"original"}
                        or feature_digest(validate_vector(remote["vector"]["original"], rows=1031)) != point["payload"]["embedding_sha256"]):
                        raise SearchUnavailable("Remote feature/payload mismatch; refused overwrite")
                    page_id = point["id"]
                    row = db.get(IndexPage, (index.id, page_id))
                    values = {"embedding_sha256": point["payload"]["embedding_sha256"], "token_count": 1031}
                    if row is None:
                        if index.status == "ready":
                            raise ValueError("Active index membership missing")
                        db.add(IndexPage(index_id=index.id, page_id=page_id, **values))
                    else:
                        match(row, values)
                db.flush()
                if len(db.scalars(select(IndexPage).where(IndexPage.index_id == index.id)).all()) != len(points):
                    raise ValueError("Extra index memberships")
                provenance = {"feature_file_sha256": bundle["source"]["files"]["page_embeddings.pt"],
                              "source_manifest_sha256": sha(canonical(bundle).encode()),
                              "page_count": len(points), "vector_count": len(points)*1031}
                if index.status == "ready":
                    match(index, provenance)
                for key, value in provenance.items():
                    setattr(index, key, value)
                index.status, profile.status = "ready", "validated"
                for doc in documents:
                    doc.status = "ready"
                db.flush()
                result = {"index_id": index.id, "collection": index.collection_name, **provenance,
                          "existing_collection_verified_without_upsert": existing, "status": "ready"}
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            raise
