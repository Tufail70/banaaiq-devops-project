"""Phase 3: Add Project.completion_summary and completion_summary_ar columns

Revision ID: 005_phase3_completion_summary
Revises: 004_phase2_distribution
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '005_phase3_completion_summary'
down_revision = '004_phase2_distribution'
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return False
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    return column_name in cols


def upgrade():
    # Add Project.completion_summary (idempotent)
    if not _has_column('projects', 'completion_summary'):
        op.add_column('projects', sa.Column('completion_summary', sa.Text(), nullable=True))

    # Add Project.completion_summary_ar (idempotent)
    if not _has_column('projects', 'completion_summary_ar'):
        op.add_column('projects', sa.Column('completion_summary_ar', sa.Text(), nullable=True))


def downgrade():
    if _has_column('projects', 'completion_summary_ar'):
        op.drop_column('projects', 'completion_summary_ar')

    if _has_column('projects', 'completion_summary'):
        op.drop_column('projects', 'completion_summary')
