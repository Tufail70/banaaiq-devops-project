"""BOQ rebuild: add new columns for distribution + versioning
Revision ID: 007_boq_rebuild
Revises: 006_phase4_inventory_source
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "007_boq_rebuild"
down_revision = "006_phase4_inventory_source"
branch_labels = None
depends_on = None


def _col_exists(conn, table, col):
    inspector = sa.inspect(conn)
    if not inspector.has_table(table):
        return False
    return col in {column["name"] for column in inspector.get_columns(table)}


def upgrade():
    conn = op.get_bind()
    cols = [
        ("parent_master_boq_id", "INTEGER REFERENCES boqs(id) ON DELETE SET NULL"),
        ("assigned_to_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
        ("trade_section", "VARCHAR(50)"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("parent_revision_id", "INTEGER REFERENCES boqs(id) ON DELETE SET NULL"),
        ("design_files_json", "TEXT"),
    ]
    for col_name, col_def in cols:
        if not _col_exists(conn, "boqs", col_name):
            op.execute(text(f"ALTER TABLE boqs ADD COLUMN {col_name} {col_def}"))
            print(f"[007] Added boqs.{col_name}")
        else:
            print(f"[007] boqs.{col_name} already exists — skip")


def downgrade():
    conn = op.get_bind()
    drop_cols = [
        col_name
        for col_name in ["design_files_json", "parent_revision_id", "version", "trade_section", "assigned_to_user_id", "parent_master_boq_id"]
        if _col_exists(conn, "boqs", col_name)
    ]
    if drop_cols:
        with op.batch_alter_table("boqs") as batch_op:
            for col_name in drop_cols:
                batch_op.drop_column(col_name)
                print(f"[007 downgrade] Dropped boqs.{col_name}")
