"""009 performance indexes"""
revision = "009_perf_indexes"
down_revision = "008_inventory_rebuild"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

INDEXES = [
    ("ix_inventory_items_project_id", "inventory_items", "project_id"),
    ("ix_inventory_items_user_project", "inventory_items", "user_id, project_id"),
    ("ix_boqs_project_id", "boqs", "project_id"),
    ("ix_boqs_assigned_to_user_id", "boqs", "assigned_to_user_id"),
    ("ix_tasks_project_id", "tasks", "project_id"),
    ("ix_dprs_project_user", "dprs", "project_id, user_id"),
    ("ix_inventory_assignments_user_project", "inventory_assignments", "assigned_user_id, project_id"),
    ("ix_project_assignments_user_id", "project_assignments", "user_id"),
]

def upgrade():
    for name, table, cols in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({cols})")

def downgrade():
    for name, table, cols in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
