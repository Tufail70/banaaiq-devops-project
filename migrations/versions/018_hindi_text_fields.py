"""018 hindi_text_fields — add name_hi to inventory_items and tasks"""
revision = "018_hindi_text_fields"
down_revision = "017_user_country_currency"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_column(table, col):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    with op.batch_alter_table("inventory_items", schema=None) as batch_op:
        if not _has_column("inventory_items", "name_hi"):
            batch_op.add_column(
                sa.Column("name_hi", sa.String(200), nullable=True)
            )

    with op.batch_alter_table("tasks", schema=None) as batch_op:
        if not _has_column("tasks", "name_hi"):
            batch_op.add_column(
                sa.Column("name_hi", sa.String(200), nullable=True)
            )


def downgrade():
    with op.batch_alter_table("inventory_items", schema=None) as batch_op:
        if _has_column("inventory_items", "name_hi"):
            batch_op.drop_column("name_hi")
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        if _has_column("tasks", "name_hi"):
            batch_op.drop_column("name_hi")
