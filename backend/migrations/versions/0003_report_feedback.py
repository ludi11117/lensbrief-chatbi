"""Add feedback linked to immutable report versions."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "report_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("body", sa.String(1200), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["report_id", "version"], ["report_version.report_id", "report_version.number"]),
    )
    op.create_index("ix_feedback_version_id", "report_feedback", ["report_id", "version", "id"])

def downgrade():
    op.drop_table("report_feedback")
