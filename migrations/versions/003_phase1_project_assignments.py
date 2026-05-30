"""Phase 1: add project_assignments table

Revision ID: 003_phase1_project_assignments
Revises: 002_phase1_project_counter
Create Date: 2026-05-02

Upgrade steps (idempotent):
  1. Create project_assignments table if not present.
     Columns: id PK, project_id FK→projects, user_id FK→users,
              role_on_project String(50), assigned_at DateTime.
     Unique constraint: (project_id, user_id) uq_project_user.
     Indexes: project_id, user_id.

Downgrade:
  Drop indexes then table cleanly.
"""

from alembic import op
import sqlalchemy as sa

revision = "003_phase1_project_assignments"
down_revision = "002_phase1_project_counter"
branch_labels = None
depends_on = None


def _table_exists(conn, table):
    return sa.inspect(conn).has_table(table)


def upgrade():
    conn = op.get_bind()

    if _table_exists(conn, "project_assignments"):
        print("[003] project_assignments already exists -- skipping CREATE")
        return

    op.create_table(
        "project_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_on_project", sa.String(50), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )
    op.create_index("ix_project_assignments_project_id", "project_assignments", ["project_id"])
    op.create_index("ix_project_assignments_user_id", "project_assignments", ["user_id"])
    print("[003] Created project_assignments table with indexes.")


def downgrade():
    conn = op.get_bind()

    if not _table_exists(conn, "project_assignments"):
        print("[003 downgrade] project_assignments does not exist -- nothing to drop")
        return

    # Use if_exists=True — db.create_all() at startup may have created the
    # table without these named indexes; downgrade must still succeed.
    op.drop_index("ix_project_assignments_user_id", table_name="project_assignments", if_exists=True)
    op.drop_index("ix_project_assignments_project_id", table_name="project_assignments", if_exists=True)
    op.drop_table("project_assignments")
    print("[003 downgrade] Dropped project_assignments table.")
