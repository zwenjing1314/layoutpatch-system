"""Persistent sessions and login failure windows; existing accounts/documents unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "0002_auth"
down_revision = "0001_metadata"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("auth_version", sa.Integer, nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Float, nullable=False),
        sa.Column("last_seen", sa.Float, nullable=False),
        sa.Column("expires_at", sa.Float, nullable=False),
        sa.Column("revoked_at", sa.Float),
        sa.CheckConstraint("length(token_hash)=64 AND auth_version >= 1", name="ck_session_identity"),
        sa.CheckConstraint("expires_at > created_at AND last_seen >= created_at", name="ck_session_times"))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("login_attempts",
        sa.Column("subject_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.Float, nullable=False),
        sa.Column("failures", sa.Integer, nullable=False),
        sa.CheckConstraint("failures >= 0", name="ck_login_failures"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore an explicit backup instead")
