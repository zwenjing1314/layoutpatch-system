"""Document authorization generation and minimal atomic sharing events."""
from alembic import op
import sqlalchemy as sa
revision = "0010_document_sharing"
down_revision = "0009_account_events"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("documents", sa.Column("access_version", sa.Integer(), sa.CheckConstraint("access_version >= 1", name="ck_document_access_version"), server_default="1", nullable=False))
    op.create_table("sharing_events",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("document_id",sa.String(36),sa.ForeignKey("documents.id"),nullable=False),
        sa.Column("action",sa.String(16),nullable=False),sa.Column("outcome",sa.String(8),nullable=False),
        sa.Column("code",sa.String(64),nullable=False),sa.Column("before_version",sa.Integer(),nullable=False),
        sa.Column("after_version",sa.Integer(),nullable=False),sa.Column("occurred_at",sa.Float(),nullable=False),
        sa.CheckConstraint("action IN ('publish','unpublish')",name="ck_sharing_action"),
        sa.CheckConstraint("outcome IN ('success','noop','rejected')",name="ck_sharing_outcome"),
        sa.CheckConstraint("before_version >= 1 AND after_version >= before_version",name="ck_sharing_versions"))
    op.create_index("ix_sharing_events_actor_id","sharing_events",["actor_id"])
    op.create_index("ix_sharing_events_document_id","sharing_events",["document_id"])

def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
