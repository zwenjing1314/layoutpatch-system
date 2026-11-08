"""Independent parser identities, immutable attempts and page candidate sets. No backfill or retrieval changes."""
from alembic import op
import sqlalchemy as sa

revision = "0008_parsing"
down_revision = "0007_job_attempts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("parser_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("config_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint("length(config_sha256)=64", name="ck_parser_profile_hash"))
    op.create_table("parsing_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("parser_profile_id", sa.String(36), sa.ForeignKey("parser_profiles.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("document_version_id", "parser_profile_id", "attempt", name="uq_parsing_attempt"),
        sa.CheckConstraint("attempt >= 1 AND attempt <= 10", name="ck_parsing_attempt"),
        sa.CheckConstraint("status IN ('queued','running','ready','partial','failed','interrupted')", name="ck_parsing_status"))
    op.create_index("ix_parsing_tasks_document_version_id", "parsing_tasks", ["document_version_id"])
    op.create_table("page_parses",
        sa.Column("task_id", sa.String(36), sa.ForeignKey("parsing_tasks.id"), primary_key=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("pages.id"), primary_key=True),
        sa.Column("render_sha256", sa.String(64), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("candidate_hash", sa.String(64)),
        sa.Column("candidates_json", sa.Text()),
        sa.Column("provenance_json", sa.Text()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status IN ('pending','running','ready','no_candidates','failed','timeout','interrupted')", name="ck_page_parse_status"),
        sa.CheckConstraint("candidate_count >= 0 AND width_px > 0 AND height_px > 0", name="ck_page_parse_counts"),
        sa.CheckConstraint("length(render_sha256)=64", name="ck_page_parse_render"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
