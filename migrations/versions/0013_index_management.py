"""Index management: durable operations and an ABA-safe active pointer."""
from alembic import op
import sqlalchemy as sa

revision = "0013_index_management"
down_revision = "0012_query_history"
branch_labels = depends_on = None


def upgrade():
    op.add_column("system_state", sa.Column("index_epoch", sa.Integer(), sa.CheckConstraint("index_epoch >= 1", name="ck_index_epoch"), nullable=False, server_default="1"))
    # SQLite ADD COLUMN cannot add a named table constraint; enforce it inline.
    # The original singleton may be absent on legacy imports; service initializes it under the writer lock.
    op.create_table("index_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("index_generations.id"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("index_generations.id"), nullable=False),
        sa.Column("expected_epoch", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("actor_id", "request_id", name="uq_index_operation_request"),
        sa.CheckConstraint("kind IN ('verify','rebuild','activate')", name="ck_index_operation_kind"),
        sa.CheckConstraint("status IN ('running','completed','failed','interrupted')", name="ck_index_operation_status"),
        sa.CheckConstraint("length(input_sha256)=64 AND expected_epoch >= 1", name="ck_index_operation_input"))
    op.create_index("ix_index_operations_actor_id", "index_operations", ["actor_id"])
    op.create_table("index_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("operation_id", sa.String(36), sa.ForeignKey("index_operations.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.Float(), nullable=False))
    op.create_index("ix_index_events_actor_id", "index_events", ["actor_id"])
    op.create_index("ix_index_events_operation_id", "index_events", ["operation_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
