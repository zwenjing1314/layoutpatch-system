"""Minimal atomic account management events; no user/data backfill."""
from alembic import op
import sqlalchemy as sa

revision = "0009_account_events"
down_revision = "0008_parsing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("account_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("target_ref", sa.String(64), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.Float(), nullable=False),
        sa.CheckConstraint("source IN ('http','cli')", name="ck_account_event_source"),
        sa.CheckConstraint("action IN ('create','enable','disable','reset','revoke')", name="ck_account_event_action"),
        sa.CheckConstraint("outcome IN ('success','noop','rejected')", name="ck_account_event_outcome"),
        sa.CheckConstraint("source='cli' OR actor_id IS NOT NULL", name="ck_account_event_actor"))
    op.create_index("ix_account_events_actor_id", "account_events", ["actor_id"])
    op.create_index("ix_account_events_target_id", "account_events", ["target_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
