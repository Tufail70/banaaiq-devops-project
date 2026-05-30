"""015 gateway_plans — cached provider plan IDs for Razorpay/Stripe"""
revision = "015_gateway_plans"
down_revision = "d5a72741821b"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_table(name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return inspector.has_table(name)


def upgrade():
    if not _has_table("gateway_plans"):
        op.create_table(
            "gateway_plans",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("cache_key", sa.String(100), nullable=False),
            sa.Column("gateway_plan_id", sa.String(100), nullable=False),
            sa.Column("plan_code", sa.String(30), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.UniqueConstraint("provider", "cache_key", name="uq_gateway_plan_provider_key"),
        )


def downgrade():
    if _has_table("gateway_plans"):
        op.drop_table("gateway_plans")
