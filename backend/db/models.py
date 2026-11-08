"""Metadata, authentication and verified index membership."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, validates

from backend.documents.names import normalize_name


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
    display_name_key: Mapped[str] = mapped_column(String, server_default="", index=True)

    @validates("display_name")
    def set_display_name(self, key, value):
        self.display_name_key = normalize_name(value)
        return value
    visibility: Mapped[str] = mapped_column(String, default="private")
    access_version: Mapped[int] = mapped_column(Integer, CheckConstraint("access_version >= 1", name="ck_document_access_version"), server_default="1", default=1)
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
    feature_file_sha256: Mapped[str | None] = mapped_column(String(64))
    source_manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String, default=now)


class IndexPage(Base):
    __tablename__ = "index_pages"
    __table_args__ = (CheckConstraint("length(embedding_sha256)=64 AND token_count=1031", name="ck_index_page_feature"),)
    index_id: Mapped[str] = mapped_column(ForeignKey("index_generations.id"), primary_key=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), primary_key=True)
    embedding_sha256: Mapped[str] = mapped_column(String(64))
    token_count: Mapped[int] = mapped_column(Integer)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "upload_key", name="uq_job_upload_key"),
        UniqueConstraint("document_version_id", name="uq_job_version"),
        CheckConstraint("kind='ingest'", name="ck_job_kind"),
        CheckConstraint("status IN ('receiving','queued','failed','interrupted','running','completed','cancelled')", name="ck_job_status"),
        CheckConstraint("attempt >= 1 AND progress >= 0 AND progress <= 100 AND upload_bytes > 0", name="ck_job_counts"),
        CheckConstraint("length(request_sha256)=64", name="ck_job_request_hash"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    upload_key: Mapped[str] = mapped_column(String(36))
    request_sha256: Mapped[str] = mapped_column(String(64))
    upload_bytes: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), default="ingest")
    stage: Mapped[str] = mapped_column(String(32), default="upload")
    status: Mapped[str] = mapped_column(String(16), default="receiving")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    cancel_requested_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        CheckConstraint("attempt >= 1 AND progress >= 0 AND progress <= 100", name="ck_attempt_counts"),
        CheckConstraint("status IN ('receiving','queued','failed','interrupted','running','completed','cancelled')", name="ck_attempt_status"),
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    attempt: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    stage: Mapped[str] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    cancel_requested_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    started_at: Mapped[str | None] = mapped_column(String)
    ended_at: Mapped[str | None] = mapped_column(String)


class SystemState(Base):
    __tablename__ = "system_state"
    __table_args__ = (CheckConstraint("id=1", name="ck_system_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_index_id: Mapped[str | None] = mapped_column(ForeignKey("index_generations.id"))


class PageFeature(Base):
    __tablename__ = "page_features"
    __table_args__ = (CheckConstraint("length(encoder_sha256)=64 AND length(tensor_sha256)=64 AND length(export_sha256)=64", name="ck_feature_hashes"),)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), primary_key=True)
    encoder_sha256: Mapped[str] = mapped_column(String(64))
    tensor_path: Mapped[str] = mapped_column(String)
    tensor_sha256: Mapped[str] = mapped_column(String(64))
    export_path: Mapped[str] = mapped_column(String)
    export_sha256: Mapped[str] = mapped_column(String(64))


class ParserProfile(Base):
    __tablename__ = "parser_profiles"
    __table_args__ = (CheckConstraint("length(config_sha256)=64", name="ck_parser_profile_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    config_json: Mapped[str] = mapped_column(Text)
    config_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class ParsingTask(Base):
    __tablename__ = "parsing_tasks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "parser_profile_id", "attempt", name="uq_parsing_attempt"),
        CheckConstraint("attempt >= 1 AND attempt <= 10", name="ck_parsing_attempt"),
        CheckConstraint("status IN ('queued','running','ready','partial','failed','interrupted')", name="ck_parsing_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    parser_profile_id: Mapped[str] = mapped_column(ForeignKey("parser_profiles.id"))
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class PageParse(Base):
    __tablename__ = "page_parses"
    __table_args__ = (
        CheckConstraint("status IN ('pending','running','ready','no_candidates','failed','timeout','interrupted')", name="ck_page_parse_status"),
        CheckConstraint("candidate_count >= 0 AND width_px > 0 AND height_px > 0", name="ck_page_parse_counts"),
        CheckConstraint("length(render_sha256)=64", name="ck_page_parse_render"),
    )
    task_id: Mapped[str] = mapped_column(ForeignKey("parsing_tasks.id"), primary_key=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id"), primary_key=True)
    render_sha256: Mapped[str] = mapped_column(String(64))
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    candidate_hash: Mapped[str | None] = mapped_column(String(64))
    candidates_json: Mapped[str | None] = mapped_column(Text)
    provenance_json: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String, default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("length(token_hash)=64 AND auth_version >= 1", name="ck_session_identity"),
        CheckConstraint("expires_at > created_at AND last_seen >= created_at", name="ck_session_times"),
    )
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    auth_version: Mapped[int] = mapped_column(Integer)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Float)
    last_seen: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)
    revoked_at: Mapped[float | None] = mapped_column(Float)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (CheckConstraint("failures >= 0", name="ck_login_failures"),)
    subject_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[float] = mapped_column(Float)
    failures: Mapped[int] = mapped_column(Integer)


class AccountEvent(Base):
    """Minimal account administration metadata; never credentials or request bodies."""
    __tablename__ = "account_events"
    __table_args__ = (
        CheckConstraint("source IN ('http','cli')", name="ck_account_event_source"),
        CheckConstraint("action IN ('create','enable','disable','reset','revoke')", name="ck_account_event_action"),
        CheckConstraint("outcome IN ('success','noop','rejected')", name="ck_account_event_outcome"),
        CheckConstraint("source='cli' OR actor_id IS NOT NULL", name="ck_account_event_actor"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    target_ref: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(8))
    action: Mapped[str] = mapped_column(String(8))
    outcome: Mapped[str] = mapped_column(String(8))
    code: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[float] = mapped_column(Float)


class SharingEvent(Base):
    """Atomic sharing decisions. No names, content, credentials or signed URLs."""
    __tablename__ = "sharing_events"
    __table_args__ = (
        CheckConstraint("action IN ('publish','unpublish')", name="ck_sharing_action"),
        CheckConstraint("outcome IN ('success','noop','rejected')", name="ck_sharing_outcome"),
        CheckConstraint("before_version >= 1 AND after_version >= before_version", name="ck_sharing_versions"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    action: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(8))
    code: Mapped[str] = mapped_column(String(64))
    before_version: Mapped[int] = mapped_column(Integer)
    after_version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[float] = mapped_column(Float)
