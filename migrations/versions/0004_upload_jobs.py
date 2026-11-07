"""Durable upload reservation, owner-scoped idempotency and processing status."""
from alembic import op
import sqlalchemy as sa

revision = "0004_upload_jobs"
down_revision = "0003_search_pages"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("upload_key", sa.String(36), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("upload_bytes", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Integer, nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.String, nullable=False),
        sa.Column("updated_at", sa.String, nullable=False),
        sa.UniqueConstraint("owner_id", "upload_key", name="uq_job_upload_key"),
        sa.UniqueConstraint("document_version_id", name="uq_job_version"),
        sa.CheckConstraint("kind='ingest'", name="ck_job_kind"),
        sa.CheckConstraint("status IN ('receiving','queued','failed','interrupted','running','completed','cancelled')", name="ck_job_status"),
        sa.CheckConstraint("attempt >= 1 AND progress >= 0 AND progress <= 100 AND upload_bytes > 0", name="ck_job_counts"),
        sa.CheckConstraint("length(request_sha256)=64", name="ck_job_request_hash"))
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
