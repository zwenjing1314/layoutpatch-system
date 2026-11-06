"""1B-2 identity tables. Profile/index rows are pending, not a usable search index."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','user')", name="ck_user_role"),
        CheckConstraint("active IN (0,1) AND must_change_password IN (0,1)", name="ck_user_flags"),
        CheckConstraint("auth_version >= 1", name="ck_auth_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64, collation="NOCASE"), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("visibility IN ('private','shared')", name="ck_visibility"),
        CheckConstraint("status IN ('registered','ready','deleted')", name="ck_document_status"),
        ForeignKeyConstraint(["id", "active_version_id"], ["document_versions.document_id", "document_versions.id"],
                             name="fk_active_version_belongs_to_document", deferrable=True, initially="DEFERRED", use_alter=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String, unique=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String)
    visibility: Mapped[str] = mapped_column(String, default="private")
    status: Mapped[str] = mapped_column(String, default="registered")
    active_version_id: Mapped[str | None] = mapped_column(String(36))
    deleted_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
        UniqueConstraint("document_id", "id", name="uq_document_version_identity"),
        CheckConstraint("version >= 1 AND page_count > 0", name="ck_version_counts"),
        CheckConstraint("length(pdf_sha256)=64 AND length(render_profile_sha256)=64", name="ck_version_hashes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    pdf_sha256: Mapped[str] = mapped_column(String(64))
    pdf_path: Mapped[str] = mapped_column(String)
    page_count: Mapped[int] = mapped_column(Integer)
    render_profile_json: Mapped[str] = mapped_column(Text)
    render_profile_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String, default=now)


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("document_version_id", "page_index", name="uq_page_order"),
        CheckConstraint("page_index >= 0 AND width_px > 0 AND height_px > 0", name="ck_page_geometry"),
        CheckConstraint("length(render_sha256)=64", name="ck_page_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    source_page_id: Mapped[str] = mapped_column(String, unique=True)
    page_index: Mapped[int] = mapped_column(Integer)
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    render_sha256: Mapped[str] = mapped_column(String(64))
    image_path: Mapped[str] = mapped_column(String)


class PipelineProfile(Base):
    __tablename__ = "pipeline_profiles"
    __table_args__ = (CheckConstraint("status IN ('pending','validated')", name="ck_profile_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, unique=True)
    config_json: Mapped[str] = mapped_column(Text)
    config_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[str] = mapped_column(String, default=now)


class IndexGeneration(Base):
    __tablename__ = "index_generations"
    __table_args__ = (
        CheckConstraint("status IN ('pending','building','ready','failed')", name="ck_index_status"),
        CheckConstraint("page_count >= 0 AND vector_count >= 0", name="ck_index_counts"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("pipeline_profiles.id"))
    collection_name: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=now)
