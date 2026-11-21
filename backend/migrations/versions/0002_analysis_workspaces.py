"""Add knowledge packs and personal analysis contexts."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "knowledge_pack",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset.id"), nullable=False),
        sa.Column("seed_key", sa.String(32), unique=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_knowledge_dataset_id", "knowledge_pack", ["dataset_id", "id"])
    op.create_table(
        "knowledge_item",
        sa.Column("pack_id", sa.Integer(), sa.ForeignKey("knowledge_pack.id"), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("metric_id", sa.Integer(), sa.ForeignKey("metric.id")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("content", sa.String(800), nullable=False),
    )
    op.create_table(
        "analysis_context",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("dataset.id"), nullable=False),
        sa.Column("knowledge_pack_id", sa.Integer(), sa.ForeignKey("knowledge_pack.id")),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("objective", sa.String(500), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("ix_context_owner_updated", "analysis_context", ["owner_id", "updated_at", "id"])
    op.execute("ALTER TABLE query_log ADD COLUMN context_id INTEGER "
               "CONSTRAINT fk_query_log_context_id_analysis_context REFERENCES analysis_context(id)")
    op.create_index("ix_query_context_created_id", "query_log", ["context_id", "created_at", "id"])
    op.execute("INSERT INTO permission (code) SELECT 'knowledge.manage' "
               "WHERE EXISTS (SELECT 1 FROM role WHERE code = 'admin')")
    op.execute("INSERT INTO role_permission (role_id, permission_code, scope) "
               "SELECT id, 'knowledge.manage', 'all' FROM role WHERE code = 'admin'")

def downgrade():
    op.execute("DELETE FROM role_permission WHERE permission_code = 'knowledge.manage'")
    op.execute("DELETE FROM permission WHERE code = 'knowledge.manage'")
    op.drop_index("ix_query_context_created_id", table_name="query_log")
    op.execute("ALTER TABLE query_log DROP COLUMN context_id")
    op.drop_table("analysis_context")
    op.drop_table("knowledge_item")
    op.drop_table("knowledge_pack")
