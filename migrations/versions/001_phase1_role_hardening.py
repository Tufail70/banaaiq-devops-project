"""Phase 1: role hardening -- rename User.role -> job_title, add access-control role column

Revision ID: 001_phase1_role_hardening
Revises:
Create Date: 2026-05-02

Upgrade steps (auditable, idempotent):
  1. Add job_title VARCHAR(50) column.
  2. Copy existing role values into job_title.
  3. Add new role VARCHAR(20) column (nullable initially).
  4. Backfill new role:
       - user owns at least one Project  -> 'project_manager'
       - job_title contains 'project manager' or ' pm ' / = 'pm'  -> 'project_manager'
       - everything else  -> 'site_engineer'
  5. Add NOT NULL + CHECK constraint on new role.
  6. Drop old role column.

Downgrade reverses exactly: drops new role, renames job_title back to role.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "001_phase1_role_hardening"
down_revision = None
branch_labels = None
depends_on = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _column_exists(conn, table, column):
    """Return True if *column* already exists in *table*."""
    inspector = sa.inspect(conn)
    if not inspector.has_table(table):
        return False
    return column in {col["name"] for col in inspector.get_columns(table)}


def _constraint_exists(conn, table, name):
    """Return True if a named constraint already exists on *table*."""
    inspector = sa.inspect(conn)
    if not inspector.has_table(table):
        return False
    for getter in (inspector.get_check_constraints, inspector.get_unique_constraints):
        try:
            if any(constraint.get("name") == name for constraint in getter(table)):
                return True
        except NotImplementedError:
            return False
    return False


def _can_alter_constraints(conn):
    return conn.dialect.name != "sqlite"


# ── upgrade ───────────────────────────────────────────────────────────────────

def upgrade():
    conn = op.get_bind()

    # ── BEFORE snapshot ───────────────────────────────────────────────────────
    total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
    print(f"\n[Phase-1] BEFORE: {total} user(s) in database")

    # ── Step 1: add job_title if not present ──────────────────────────────────
    if not _column_exists(conn, "users", "job_title"):
        op.add_column("users", sa.Column("job_title", sa.String(50), nullable=True, server_default=""))
        # Copy existing role values into the new job_title column
        conn.execute(text("UPDATE users SET job_title = role"))
        print("[Phase-1] Copied users.role -> users.job_title")
    else:
        print("[Phase-1] users.job_title already present -- skipping copy")

    # ── Step 2: add new access-control role column (nullable for backfill) ────
    if not _column_exists(conn, "users", "new_role_tmp"):
        # Use a temp name to avoid collision with the existing role column
        op.add_column("users", sa.Column("new_role_tmp", sa.String(20), nullable=True))
        print("[Phase-1] Added users.new_role_tmp (temp name during backfill)")

    # ── Step 3: backfill new role ─────────────────────────────────────────────

    # Rule A -- user owns at least one project (most authoritative signal)
    conn.execute(text(
        "UPDATE users SET new_role_tmp = 'project_manager' "
        "WHERE id IN (SELECT DISTINCT user_id FROM projects)"
    ))

    # Rule B -- job_title text contains 'project manager' or bare 'pm'
    conn.execute(text(
        "UPDATE users SET new_role_tmp = 'project_manager' "
        "WHERE new_role_tmp IS NULL "
        "  AND (LOWER(job_title) LIKE '%project manager%' "
        "       OR LOWER(job_title) LIKE '% pm %' "
        "       OR LOWER(job_title) = 'pm')"
    ))

    # Rule C -- everything else -> site_engineer
    conn.execute(text(
        "UPDATE users SET new_role_tmp = 'site_engineer' "
        "WHERE new_role_tmp IS NULL"
    ))

    # ── AFTER counts + samples ────────────────────────────────────────────────
    pm_count = conn.execute(
        text("SELECT COUNT(*) FROM users WHERE new_role_tmp = 'project_manager'")
    ).scalar() or 0
    se_count = conn.execute(
        text("SELECT COUNT(*) FROM users WHERE new_role_tmp = 'site_engineer'")
    ).scalar() or 0
    print(f"[Phase-1] AFTER backfill: {pm_count} project_manager(s), {se_count} site_engineer(s)")

    pm_sample = conn.execute(text(
        "SELECT id, email, job_title, new_role_tmp FROM users "
        "WHERE new_role_tmp = 'project_manager' LIMIT 5"
    )).fetchall()
    se_sample = conn.execute(text(
        "SELECT id, email, job_title, new_role_tmp FROM users "
        "WHERE new_role_tmp = 'site_engineer' LIMIT 5"
    )).fetchall()

    print("[Phase-1] Sample project_managers (up to 5):")
    for row in pm_sample:
        print(f"  id={row[0]}  email={row[1]!r}  job_title={row[2]!r}  -> role={row[3]!r}")

    print("[Phase-1] Sample site_engineers (up to 5):")
    for row in se_sample:
        print(f"  id={row[0]}  email={row[1]!r}  job_title={row[2]!r}  -> role={row[3]!r}")

    # ── Step 4: drop the old role column ─────────────────────────────────────
    if _column_exists(conn, "users", "role"):
        op.drop_column("users", "role")
        print("[Phase-1] Dropped old users.role column")

    # ── Step 5: rename new_role_tmp -> role ────────────────────────────────────
    if _column_exists(conn, "users", "new_role_tmp"):
        op.alter_column("users", "new_role_tmp", new_column_name="role",
                        existing_type=sa.String(20))
        print("[Phase-1] Renamed new_role_tmp -> role")

    # ── Step 6: add NOT NULL constraint ───────────────────────────────────────
    if conn.dialect.name != "sqlite":
        op.alter_column("users", "role",
                        existing_type=sa.String(20),
                        nullable=False)
    else:
        print("[Phase-1] SQLite does not support ALTER COLUMN SET NOT NULL -- skipping")

    # ── Step 7: add CHECK constraint ─────────────────────────────────────────
    if _can_alter_constraints(conn) and not _constraint_exists(conn, "users", "ck_users_role_values"):
        op.create_check_constraint(
            "ck_users_role_values",
            "users",
            "role IN ('project_manager', 'site_engineer')",
        )
        print("[Phase-1] Added CHECK constraint ck_users_role_values")
    elif conn.dialect.name == "sqlite":
        print("[Phase-1] SQLite does not support ALTER TABLE ADD CHECK -- skipping")

    print("[Phase-1] Migration complete.\n")


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade():
    conn = op.get_bind()

    # Remove CHECK constraint
    if _can_alter_constraints(conn) and _constraint_exists(conn, "users", "ck_users_role_values"):
        op.drop_constraint("ck_users_role_values", "users", type_="check")

    # Drop the access-control role column
    if _column_exists(conn, "users", "role"):
        op.drop_column("users", "role")

    # Rename job_title back to role
    if _column_exists(conn, "users", "job_title"):
        op.alter_column("users", "job_title", new_column_name="role",
                        existing_type=sa.String(50))

    print("[Phase-1 downgrade] Restored users.role from job_title; dropped access-control role column.")
