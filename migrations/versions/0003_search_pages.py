"""Bind indexed pages and their feature provenance to an index generation."""
from alembic import op
import sqlalchemy as sa

revision = "0003_search_pages"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("index_generations", sa.Column("feature_file_sha256", sa.String(64)))
    op.add_column("index_generations", sa.Column("source_manifest_sha256", sa.String(64)))
    op.create_table("index_pages",
        sa.Column("index_id", sa.String(36), sa.ForeignKey("index_generations.id"), primary_key=True),
        sa.Column("page_id", sa.String(36), sa.ForeignKey("pages.id"), primary_key=True),
        sa.Column("embedding_sha256", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.CheckConstraint("length(embedding_sha256)=64 AND token_count=1031", name="ck_index_page_feature"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
