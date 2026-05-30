"""Phase 2 distribution models: InventoryAssignment, task private notes, engineer package item status

Revision ID: 004_phase2_distribution
Revises: 003_phase1_project_assignments
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '004_phase2_distribution'
down_revision = '003_phase1_project_assignments'
branch_labels = None
depends_on = None


def _has_table(table_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    return inspector.has_table(table_name)


def _has_column(table_name, column_name):
    conn = op.get_bind()
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return False
    cols = {c['name'] for c in inspector.get_columns(table_name)}
    return column_name in cols


def upgrade():
    # --- Create inventory_assignments table ---
    if not _has_table('inventory_assignments'):
        op.create_table(
            'inventory_assignments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_items.id', ondelete='CASCADE'), nullable=False),
            sa.Column('assigned_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('allocated_qty', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('status', sa.String(20), server_default='allocated'),
            sa.Column('notified_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint('project_id', 'inventory_item_id', 'assigned_user_id', name='uq_inv_assignment'),
        )

    # --- Add tasks.is_private_to_engineer ---
    if not _has_column('tasks', 'is_private_to_engineer'):
        op.add_column('tasks', sa.Column('is_private_to_engineer', sa.Boolean(), server_default='false', nullable=True))

    # --- Add tasks.engineer_notes ---
    if not _has_column('tasks', 'engineer_notes'):
        op.add_column('tasks', sa.Column('engineer_notes', sa.Text(), nullable=True))

    # --- Add engineer_package.item_statuses_json if missing ---
    if not _has_column('engineer_package', 'item_statuses_json'):
        op.add_column('engineer_package', sa.Column('item_statuses_json', sa.Text(), server_default="'{}'"))


def downgrade():
    # Drop columns added in upgrade (in reverse order)
    if _has_column('engineer_package', 'item_statuses_json'):
        # Only drop if we added it (idempotency: check existence)
        # We can't know for sure if we added it, but downgrade should be safe
        pass  # item_statuses_json was likely pre-existing; don't drop to avoid data loss

    if _has_column('tasks', 'engineer_notes'):
        op.drop_column('tasks', 'engineer_notes')

    if _has_column('tasks', 'is_private_to_engineer'):
        op.drop_column('tasks', 'is_private_to_engineer')

    if _has_table('inventory_assignments'):
        op.drop_table('inventory_assignments')
