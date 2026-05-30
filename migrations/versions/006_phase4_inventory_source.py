"""Phase 4: Add inventory_items.source column for AI-generated tracking

Revision ID: 006_phase4_inventory_source
Revises: 005_phase3_completion_summary
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '006_phase4_inventory_source'
down_revision = '005_phase3_completion_summary'
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
    # Add inventory_items.source (idempotent)
    # Values: 'manual', 'ai_generated_master', 'bulk_upload', 'engineer_added'
    if not _has_column('inventory_items', 'source'):
        op.add_column(
            'inventory_items',
            sa.Column(
                'source',
                sa.String(length=30),
                nullable=True,
                server_default='manual',
            )
        )
    # Add inventory_items.name_ar (optional Arabic name field)
    if not _has_column('inventory_items', 'name_ar'):
        op.add_column(
            'inventory_items',
            sa.Column('name_ar', sa.String(length=200), nullable=True)
        )


def downgrade():
    if _has_column('inventory_items', 'name_ar'):
        op.drop_column('inventory_items', 'name_ar')

    if _has_column('inventory_items', 'source'):
        op.drop_column('inventory_items', 'source')
