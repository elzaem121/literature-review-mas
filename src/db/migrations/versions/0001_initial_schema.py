"""Create the pgvector extension and the users, reviews, runs, papers and chunks tables.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_step", sa.Text(), nullable=False),
        sa.Column("status_message", sa.Text(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", TIMESTAMP),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_runs_status",
        ),
    )
    op.create_table(
        "papers",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("openalex_id", sa.Text(), nullable=False, unique=True),
        sa.Column("doi", sa.Text(), unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer()),
        sa.Column("authors", postgresql.JSONB(), nullable=False),
        sa.Column("venue", sa.Text()),
        sa.Column("pdf_url", sa.Text()),
        sa.Column("ingestion_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "ingestion_status IN ('pending', 'downloaded', 'chunked', 'pdf_unavailable', 'failed')",
            name="ck_papers_ingestion_status",
        ),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("chunker_version", sa.Text(), nullable=False),
        sa.UniqueConstraint("paper_id", "ordinal", name="uq_chunks_paper_id_ordinal"),
    )


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("papers")
    op.drop_table("runs")
    op.drop_table("reviews")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
