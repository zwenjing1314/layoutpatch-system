from dataclasses import asdict, dataclass
import hashlib
import json

from sqlalchemy import and_, select
from fastapi import HTTPException

from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Page, PipelineProfile, SystemState, User
from backend.db.seed import canonical, sha
from backend.documents.access import readable_document, visible_document
from .qdrant import SearchUnavailable


@dataclass(frozen=True)
class ScopedPage:
    id: str
    document_id: str
    version_id: str
    owner_id: str
    visibility: str
    document_name: str
    page_index: int
    width_px: int
    height_px: int
    render_sha256: str
    embedding_sha256: str
    access_version: int = 1


@dataclass(frozen=True)
class AllowedScope:
    profile_id: str
    encoder_sha256: str
    index_id: str
    collection: str
    index_page_count: int
    feature_file_sha256: str
    source_manifest_sha256: str
    pages: tuple[ScopedPage, ...]
    target_document_id: str | None = None
    index_epoch: int = 1

    @property
    def fingerprint(self):
        return sha(canonical(asdict(self)).encode())


def active_index(db):
    statement = select(IndexGeneration, PipelineProfile).join(PipelineProfile).where(
        IndexGeneration.status == "ready", PipelineProfile.status == "validated")
    state = db.get(SystemState, 1)
    if state and state.active_index_id:
        statement = statement.where(IndexGeneration.id == state.active_index_id)
    rows = db.execute(statement).all()
    if len(rows) != 1:
        raise SearchUnavailable("No single validated index")
    return rows[0]


def index_epoch(db):
    state = db.get(SystemState, 1)
    return state.index_epoch if state else 1


def profile_identity(profile):
    """One frozen full-vector profile; no user supplied encoder or paths."""
    try:
        encoder_bytes = (ROOT / "configs/colpali_local.json").read_bytes()
        config = json.loads(profile.config_json)
        if (profile.name != "colpali_full_v1" or sha(profile.config_json.encode()) != profile.config_sha256
            or config["encoder"] != json.loads(encoder_bytes)
            or config["qdrant_design"] != {"vector_name": "original", "dimension": 128, "distance": "Dot", "multivector": "MAX_SIM", "exact": True}
            or any(config["render"].get(k) != v for k, v in {"dpi": 144, "colorspace": "RGB", "format": "PNG"}.items())):
            raise ValueError()
        return sha(encoder_bytes)
    except (ValueError, KeyError, TypeError, OSError):
        raise SearchUnavailable("Profile provenance mismatch") from None


def allowed_scope(db, user, document_id=None):
    if document_id is not None:
        doc = db.scalar(select(Document).join(User, User.id == Document.owner_id)
                        .where(Document.id == document_id, visible_document(user)))
        if doc is None:
            raise HTTPException(404, "DOCUMENT_NOT_FOUND")
        if doc.status != "ready" or doc.active_version_id is None:
            raise HTTPException(409, "DOCUMENT_NOT_READY")
    index, profile = active_index(db)
    encoder_sha = profile_identity(profile)
    if not index.feature_file_sha256 or not index.source_manifest_sha256:
        raise SearchUnavailable("Index provenance missing")
    # The owner must be an active administrator for shared documents. Admin's
    # ordinary search gets the same own+shared rule, never a global bypass.
    statement = (select(Document, DocumentVersion).join(User, User.id == Document.owner_id)
                      .join(DocumentVersion, and_(DocumentVersion.id == Document.active_version_id,
                                                  DocumentVersion.document_id == Document.id))
                      .where(readable_document(user)))
    if document_id is not None:
        statement = statement.where(Document.id == document_id)
    docs = db.execute(statement.order_by(Document.id)).all()
    if document_id is not None and not docs:
        raise SearchUnavailable("Selected document has no valid active version")
    pages = []
    for doc, version in docs:
        entries = db.execute(select(Page, IndexPage).join(IndexPage, IndexPage.page_id == Page.id)
                             .where(Page.document_version_id == version.id, IndexPage.index_id == index.id)
                             .order_by(Page.page_index)).all()
        if [p.page_index for p, _ in entries] != list(range(version.page_count)):
            raise SearchUnavailable("Incomplete indexed document")
        pages.extend(ScopedPage(p.id, doc.id, version.id, doc.owner_id, doc.visibility, doc.display_name,
                                p.page_index, p.width_px, p.height_px, p.render_sha256, ip.embedding_sha256, doc.access_version)
                     for p, ip in entries)
    return AllowedScope(profile.id, encoder_sha, index.id, index.collection_name,
                        index.page_count, index.feature_file_sha256, index.source_manifest_sha256, tuple(pages), document_id, index_epoch(db))
