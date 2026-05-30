"""011 inventory rich schema — specification, brands, storage, safety, alternatives, shelf life + stock request urgency"""
revision = "011_inventory_rich_schema"
down_revision = "010_inventory_lineage"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    # ── inventory_items — rich procurement schema ────────────────────────────
    new_inv_cols = [
        ("specification",           sa.Text()),
        ("brand_suggestions_json",  sa.Text()),
        ("storage_requirements",    sa.Text()),
        ("reorder_lead_time_days",  sa.Integer()),
        ("min_order_qty",           sa.Numeric(12, 2)),
        ("min_order_unit",          sa.String(50)),
        ("safety_notes",            sa.Text()),
        ("alternative_items_json",  sa.Text()),
        ("shelf_life_days",         sa.Integer()),
        ("shelf_life_note",         sa.Text()),
    ]
    with op.batch_alter_table("inventory_items") as batch_op:
        for col_name, col_type in new_inv_cols:
            if not _has_column("inventory_items", col_name):
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))

    # ── stock_requests — urgency + preferred brand + specification ───────────
    new_sr_cols = [
        ("urgency",                  sa.String(20)),
        ("preferred_brand",          sa.String(200)),
        ("specification_requested",  sa.Text()),
    ]
    with op.batch_alter_table("stock_requests") as batch_op:
        for col_name, col_type in new_sr_cols:
            if not _has_column("stock_requests", col_name):
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade():
    inv_drop = [
        "specification", "brand_suggestions_json", "storage_requirements",
        "reorder_lead_time_days", "min_order_qty", "min_order_unit",
        "safety_notes", "alternative_items_json", "shelf_life_days", "shelf_life_note",
    ]
    with op.batch_alter_table("inventory_items") as batch_op:
        for col_name in inv_drop:
            if _has_column("inventory_items", col_name):
                batch_op.drop_column(col_name)

    sr_drop = ["urgency", "preferred_brand", "specification_requested"]
    with op.batch_alter_table("stock_requests") as batch_op:
        for col_name in sr_drop:
            if _has_column("stock_requests", col_name):
                batch_op.drop_column(col_name)
