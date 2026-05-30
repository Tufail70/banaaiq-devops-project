"""add user session_token and password_updated_at

Revision ID: d5a72741821b
Revises: b4d7f1a92fb6
Create Date: 2026-05-19 17:32:04.947567

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd5a72741821b'
down_revision = 'b4d7f1a92fb6'
branch_labels = None
depends_on = None


def upgrade():
    import secrets as _secrets

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session_token', sa.String(length=64), nullable=True, server_default=''))
        batch_op.add_column(sa.Column('password_updated_at', sa.DateTime(), nullable=True))

    # Backfill: give every existing user a unique session token
    conn = op.get_bind()
    users = conn.execute(sa.text('SELECT id FROM users')).fetchall()
    for row in users:
        token = _secrets.token_hex(32)
        conn.execute(
            sa.text('UPDATE users SET session_token = :token WHERE id = :uid'),
            {'token': token, 'uid': row[0]},
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('password_updated_at')
        batch_op.drop_column('session_token')
