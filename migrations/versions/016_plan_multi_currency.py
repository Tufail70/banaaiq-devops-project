"""016 plan_multi_currency — add INR/USD native prices + default_currency to plan"""
revision = "016_plan_multi_currency"
down_revision = "015_gateway_plans"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_column(table, col):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    with op.batch_alter_table("plan", schema=None) as batch_op:
        if not _has_column("plan", "price_inr"):
            batch_op.add_column(sa.Column("price_inr", sa.Numeric(10, 2), nullable=True))
        if not _has_column("plan", "price_inr_annual"):
            batch_op.add_column(sa.Column("price_inr_annual", sa.Numeric(10, 2), nullable=True))
        if not _has_column("plan", "price_usd"):
            batch_op.add_column(sa.Column("price_usd", sa.Numeric(10, 2), nullable=True))
        if not _has_column("plan", "default_currency"):
            batch_op.add_column(
                sa.Column("default_currency", sa.String(3), nullable=True,
                          server_default="INR")
            )

    # Backfill native INR prices (₹1,499 Starter / ₹3,999 Pro)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE plan SET price_inr = 1499, price_inr_annual = 14990 "
            "WHERE name = 'starter'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE plan SET price_inr = 3999, price_inr_annual = 39990 "
            "WHERE name = 'professional'"
        )
    )
    # Also update invoice default currency default (new invoices should be INR)
    if _has_column("invoice", "currency"):
        # Don't change existing SAR invoices — only affects new rows via model default
        pass


def downgrade():
    with op.batch_alter_table("plan", schema=None) as batch_op:
        for col in ("price_inr", "price_inr_annual", "price_usd", "default_currency"):
            if _has_column("plan", col):
                batch_op.drop_column(col)
