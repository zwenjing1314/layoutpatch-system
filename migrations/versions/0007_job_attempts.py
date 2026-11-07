"""Durable attempt history and cooperative cancellation, without replacing old rows."""
from alembic import op
import sqlalchemy as sa

revision = "0007_job_attempts"
down_revision = "0006_document_names"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("cancel_requested_at", sa.String(), nullable=True))
    op.create_table("job_attempts",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("attempt", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("cancel_requested_at", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("started_at", sa.String()),
        sa.Column("ended_at", sa.String()),
        sa.CheckConstraint("attempt >= 1 AND progress >= 0 AND progress <= 100", name="ck_attempt_counts"),
        sa.CheckConstraint("status IN ('receiving','queued','failed','interrupted','running','completed','cancelled')", name="ck_attempt_status"))
    op.execute("""INSERT INTO job_attempts
        (job_id,attempt,status,stage,progress,error_code,created_at,updated_at,started_at,ended_at)
        SELECT id,attempt,status,stage,progress,error_code,created_at,updated_at,
        CASE WHEN status='running' THEN updated_at END,
        CASE WHEN status IN ('failed','interrupted','completed','cancelled') THEN updated_at END FROM jobs""")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
