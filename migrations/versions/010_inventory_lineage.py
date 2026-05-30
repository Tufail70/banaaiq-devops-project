"""010 inventory lineage — parent_batch_id for upload-revise history"""
revision = "010_inventory_lineage"
down_revision = "009_perf_indexes"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if not _has_column("inventory_items", "parent_batch_id"):
        with op.batch_alter_table("inventory_items") as batch_op:
            batch_op.add_column(sa.Column("parent_batch_id", sa.String(40), nullable=True))


def downgrade():
    if _has_column("inventory_items", "parent_batch_id"):
        with op.batch_alter_table("inventory_items") as batch_op:
            batch_op.drop_column("parent_batch_id")
