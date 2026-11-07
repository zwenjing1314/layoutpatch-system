"""Active immutable index generation pointer and full page feature provenance."""
from alembic import op
import sqlalchemy as sa

revision = "0005_ingestion"
down_revision = "0004_upload_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("system_state", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("active_index_id", sa.String(36), sa.ForeignKey("index_generations.id")),
                    sa.CheckConstraint("id=1", name="ck_system_singleton"))
    op.execute("INSERT INTO system_state(id, active_index_id) SELECT 1, CASE WHEN count(*)=1 THEN min(id) ELSE NULL END FROM index_generations WHERE status='ready'")
    op.create_table("page_features", sa.Column("page_id", sa.String(36), sa.ForeignKey("pages.id"), primary_key=True),
        sa.Column("encoder_sha256", sa.String(64), nullable=False),
        sa.Column("tensor_path", sa.String, nullable=False), sa.Column("tensor_sha256", sa.String(64), nullable=False),
        sa.Column("export_path", sa.String, nullable=False), sa.Column("export_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(encoder_sha256)=64 AND length(tensor_sha256)=64 AND length(export_sha256)=64", name="ck_feature_hashes"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
