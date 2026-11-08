"""Durable owner deletion and retryable cleanup; existing data untouched."""
from alembic import op
import sqlalchemy as sa

revision = "0011_document_deletion"
down_revision = "0010_document_sharing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("document_cleanups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status IN ('queued','running','failed','completed')", name="ck_cleanup_status"),
        sa.CheckConstraint("attempt >= 1", name="ck_cleanup_attempt"))
    op.create_table("deletion_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.Float(), nullable=False),
        sa.CheckConstraint("action IN ('delete','retry','cleanup')", name="ck_deletion_action"),
        sa.CheckConstraint("outcome IN ('success','noop','rejected','failed')", name="ck_deletion_outcome"),
        sa.CheckConstraint("attempt >= 1", name="ck_deletion_attempt"))
    op.create_index("ix_deletion_events_document_id", "deletion_events", ["document_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
