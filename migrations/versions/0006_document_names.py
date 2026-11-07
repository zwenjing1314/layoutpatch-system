"""Normalized document filename key; additive SQLite migration, no table rebuild."""
from alembic import op
import sqlalchemy as sa
import unicodedata

revision = "0006_document_names"
down_revision = "0005_ingestion"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("display_name_key", sa.String(), nullable=False, server_default=""))
    bind = op.get_bind()
    for row in bind.execute(sa.text("SELECT id, display_name FROM documents")).mappings().all():
        bind.execute(sa.text("UPDATE documents SET display_name_key=:key WHERE id=:id"),
                     {"id": row["id"], "key": unicodedata.normalize("NFKC", row["display_name"]).casefold()})
    op.create_index("ix_documents_display_name_key", "documents", ["display_name_key"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
