from dataclasses import asdict, dataclass
import hashlib
import json

from sqlalchemy import and_, select

from backend.db.connection import ROOT
from backend.db.models import Document, DocumentVersion, IndexGeneration, IndexPage, Page, PipelineProfile, User
from backend.db.seed import canonical, sha
from backend.documents.access import readable_document
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

    @property
    def fingerprint(self):
        return sha(canonical(asdict(self)).encode())


def allowed_scope(db, user):
    rows = db.execute(select(IndexGeneration, PipelineProfile).join(PipelineProfile)
                      .where(IndexGeneration.status == "ready", PipelineProfile.status == "validated")).all()
    if len(rows) != 1:
        raise SearchUnavailable("No single validated index")
    index, profile = rows[0]
    try:
        config = json.loads(profile.config_json)
        encoder_bytes = (ROOT / "configs/colpali_local.json").read_bytes()
        if (sha(profile.config_json.encode()) != profile.config_sha256 or config["encoder"] != json.loads(encoder_bytes)
            or config["qdrant_design"] != {"vector_name": "original", "dimension": 128, "distance": "Dot", "multivector": "MAX_SIM", "exact": True}
            or not index.feature_file_sha256 or not index.source_manifest_sha256):
            raise ValueError()
    except (ValueError, KeyError, OSError):
        raise SearchUnavailable("Profile provenance mismatch") from None
    # The owner must be an active administrator for shared documents. Admin's
    # ordinary search gets the same own+shared rule, never a global bypass.
    docs = db.execute(select(Document, DocumentVersion).join(User, User.id == Document.owner_id)
                      .join(DocumentVersion, and_(DocumentVersion.id == Document.active_version_id,
                                                  DocumentVersion.document_id == Document.id))
                      .where(readable_document(user))
                      .order_by(Document.id)).all()
    pages = []
    for doc, version in docs:
        entries = db.execute(select(Page, IndexPage).join(IndexPage, IndexPage.page_id == Page.id)
                             .where(Page.document_version_id == version.id, IndexPage.index_id == index.id)
                             .order_by(Page.page_index)).all()
        if [p.page_index for p, _ in entries] != list(range(version.page_count)):
            raise SearchUnavailable("Incomplete indexed document")
        pages.extend(ScopedPage(p.id, doc.id, version.id, doc.owner_id, doc.visibility, doc.display_name,
                                p.page_index, p.width_px, p.height_px, p.render_sha256, ip.embedding_sha256)
                     for p, ip in entries)
    return AllowedScope(profile.id, hashlib.sha256(encoder_bytes).hexdigest(), index.id, index.collection_name,
                        index.page_count, index.feature_file_sha256, index.source_manifest_sha256, tuple(pages))
