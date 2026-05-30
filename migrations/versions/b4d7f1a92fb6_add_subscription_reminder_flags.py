"""add subscription reminder flags

Revision ID: b4d7f1a92fb6
Revises: 012_tasks_rebuild
Create Date: 2026-05-19 16:46:12.029538

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b4d7f1a92fb6'
down_revision = '012_tasks_rebuild'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('subscription', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reminder_3d_sent', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('reminder_1d_sent', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('subscription', schema=None) as batch_op:
        batch_op.drop_column('reminder_1d_sent')
        batch_op.drop_column('reminder_3d_sent')
