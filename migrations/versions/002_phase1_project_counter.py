"""Phase 1: add project_counters table for race-safe BIQ code generation

Revision ID: 002_phase1_project_counter
Revises: 001_phase1_role_hardening
Create Date: 2026-05-02

Upgrade steps (idempotent):
  1. Create project_counters table if it does not already exist.
     Columns: year (Integer PK), last_seq (Integer NOT NULL default 0),
              updated_at (DateTime).
  No data backfill -- database has zero projects at migration time.

Downgrade:
  Drop project_counters table if it exists.
"""

from alembic import op
import sqlalchemy as sa

revision = "002_phase1_project_counter"
down_revision = "001_phase1_role_hardening"
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    return sa.inspect(conn).has_table(table)


def upgrade():
    conn = op.get_bind()

    if _table_exists(conn, "project_counters"):
        print("[002] project_counters already exists -- skipping CREATE")
        return

    op.create_table(
        "project_counters",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("year"),
    )
    print("[002] Created project_counters table.")


def downgrade():
    conn = op.get_bind()

    if not _table_exists(conn, "project_counters"):
        print("[002 downgrade] project_counters does not exist -- nothing to drop")
        return

    op.drop_table("project_counters")
    print("[002 downgrade] Dropped project_counters table.")
