"""Private query history, idempotency markers and minimal mutation events."""
from alembic import op
import sqlalchemy as sa

revision = "0012_query_history"
down_revision = "0011_document_deletion"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("query_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("history_id", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_query_request_owner_key"),
        sa.CheckConstraint("status IN ('running','completed','failed','interrupted','deleted')", name="ck_query_request_status"),
        sa.CheckConstraint("length(input_sha256)=64", name="ck_query_request_hash"))
    op.create_index("ix_query_requests_owner_id", "query_requests", ["owner_id"])
    op.create_table("query_histories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_row_id", sa.String(36), sa.ForeignKey("query_requests.id"), nullable=False, unique=True),
        sa.Column("original_title", sa.String(100), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("q", sa.Text(), nullable=False),
        sa.Column("k", sa.Integer(), nullable=False),
        sa.Column("search_mode", sa.String(16), nullable=False),
        sa.Column("target_document_id", sa.String(36)),
        sa.Column("target_version_id", sa.String(36)),
        sa.Column("target_access_version", sa.Integer()),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("encoder_sha256", sa.String(64), nullable=False),
        sa.Column("index_generation", sa.String(36), nullable=False),
        sa.Column("scope_version", sa.String(64), nullable=False),
        sa.Column("result_status", sa.String(8), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("timings_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("pinned_at", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("k >= 1 AND k <= 50 AND hit_count >= 0 AND hit_count <= k", name="ck_query_history_counts"),
        sa.CheckConstraint("version >= 1", name="ck_query_history_version"),
        sa.CheckConstraint("search_mode IN ('library','document') AND result_status IN ('ok','empty')", name="ck_query_history_states"),
        sa.CheckConstraint("length(q) BETWEEN 1 AND 2000 AND length(title) BETWEEN 1 AND 100 AND length(original_title) BETWEEN 1 AND 100", name="ck_query_history_text"))
    op.create_index("ix_query_histories_owner_id", "query_histories", ["owner_id"])
    op.create_table("query_history_hits",
        sa.Column("history_id", sa.String(36), sa.ForeignKey("query_histories.id"), primary_key=True),
        sa.Column("page_rank", sa.Integer(), primary_key=True),
        sa.Column("page_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("document_version_id", sa.String(36), nullable=False),
        sa.Column("render_sha256", sa.String(64), nullable=False),
        sa.Column("embedding_sha256", sa.String(64), nullable=False),
        sa.Column("access_version", sa.Integer(), nullable=False),
        sa.Column("page_score", sa.Float(), nullable=False),
        sa.UniqueConstraint("history_id", "page_id", name="uq_query_history_page"),
        sa.CheckConstraint("page_rank >= 1 AND page_rank <= 50 AND access_version >= 1", name="ck_query_history_hit_counts"))
    op.create_table("history_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("history_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.Float(), nullable=False),
        sa.CheckConstraint("action IN ('create','update','delete')", name="ck_history_event_action"),
        sa.CheckConstraint("outcome IN ('success','noop') AND version >= 1", name="ck_history_event_result"))
    op.create_index("ix_history_events_actor_id", "history_events", ["actor_id"])
    op.create_index("ix_history_events_history_id", "history_events", ["history_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore explicit backup")
