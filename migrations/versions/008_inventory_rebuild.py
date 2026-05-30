"""008 inventory rebuild — new columns + stock_requests table"""
revision = "008_inventory_rebuild"
down_revision = "007_boq_rebuild"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    def col_exists(table, col):
        if not inspector.has_table(table):
            return False
        return col in {column["name"] for column in inspector.get_columns(table)}

    def table_exists(table):
        return inspector.has_table(table)

    # inventory_items new columns
    for col, ddl in [
        ("category_ar", "VARCHAR(80)"),
        ("name_ar", "VARCHAR(200)"),
        ("design_files_json", "TEXT"),
        ("master_inventory_batch_id", "VARCHAR(40)"),
    ]:
        if not col_exists("inventory_items", col):
            op.execute(f"ALTER TABLE inventory_items ADD COLUMN {col} {ddl}")

    # source column (added in phase 4 — ensure exists)
    if not col_exists("inventory_items", "source"):
        op.execute("ALTER TABLE inventory_items ADD COLUMN source VARCHAR(30) DEFAULT 'manual'")

    # usage_logs new columns
    for col, ddl in [
        ("project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL"),
        ("notes", "TEXT"),
        ("notes_lang", "VARCHAR(10)"),
    ]:
        if not col_exists("usage_logs", col):
            op.execute(f"ALTER TABLE usage_logs ADD COLUMN {col} {ddl}")

    # stock_requests table
    if not table_exists("stock_requests"):
        op.create_table(
            "stock_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("inventory_item_id", sa.Integer(), sa.ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("requested_qty", sa.Numeric(12, 2), nullable=False),
            sa.Column("unit", sa.String(20), nullable=True),
            sa.Column("proposed_item_name", sa.String(200), nullable=True),
            sa.Column("proposed_item_name_ar", sa.String(200), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("description_lang", sa.String(10), nullable=True),
            sa.Column("attached_files_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("approved_qty", sa.Numeric(12, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_stock_requests_project_status", "stock_requests", ["project_id", "status"])


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("stock_requests"):
        op.drop_index("ix_stock_requests_project_status", table_name="stock_requests", if_exists=True)
        op.drop_table("stock_requests")

    inspector = sa.inspect(conn)
    if inspector.has_table("inventory_items"):
        existing = {column["name"] for column in inspector.get_columns("inventory_items")}
        drop_cols = [col for col in ["category_ar", "name_ar", "design_files_json", "master_inventory_batch_id"] if col in existing]
        if drop_cols:
            with op.batch_alter_table("inventory_items") as batch_op:
                for col in drop_cols:
                    batch_op.drop_column(col)

    inspector = sa.inspect(conn)
    if inspector.has_table("usage_logs"):
        existing = {column["name"] for column in inspector.get_columns("usage_logs")}
        drop_cols = [col for col in ["project_id", "notes", "notes_lang"] if col in existing]
        if drop_cols:
            with op.batch_alter_table("usage_logs") as batch_op:
                for col in drop_cols:
                    batch_op.drop_column(col)
