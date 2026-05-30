"""017 user_country_currency — add country, preferred_currency, gstin to users + buyer_gstin to invoice"""
revision = "017_user_country_currency"
down_revision = "016_plan_multi_currency"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_column(table, col):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return col in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        if not _has_column("users", "country"):
            batch_op.add_column(
                sa.Column("country", sa.String(10), nullable=True, server_default="IN")
            )
        if not _has_column("users", "preferred_currency"):
            batch_op.add_column(
                sa.Column("preferred_currency", sa.String(3), nullable=True, server_default="INR")
            )
        if not _has_column("users", "gstin"):
            batch_op.add_column(
                sa.Column("gstin", sa.String(20), nullable=True)
            )

    with op.batch_alter_table("invoice", schema=None) as batch_op:
        if not _has_column("invoice", "buyer_gstin"):
            batch_op.add_column(
                sa.Column("buyer_gstin", sa.String(20), nullable=True)
            )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        for col in ("country", "preferred_currency", "gstin"):
            if _has_column("users", col):
                batch_op.drop_column(col)
    with op.batch_alter_table("invoice", schema=None) as batch_op:
        if _has_column("invoice", "buyer_gstin"):
            batch_op.drop_column("buyer_gstin")
