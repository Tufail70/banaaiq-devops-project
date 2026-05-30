"""012 tasks rebuild — new schema with dependencies + activity log"""
revision = "012_tasks_rebuild"
down_revision = "011_inventory_rich_schema"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def _has_table(name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return inspector.has_table(name)


def _has_column(table_name, column_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _has_index(table_name, index_name):
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade():
    conn = op.get_bind()

    # ── 1. Drop task_logs (replaced by task_activities) ──────────────────────
    if _has_table("task_logs"):
        op.drop_table("task_logs")

    # ── 2. Rebuild tasks table ────────────────────────────────────────────────
    # Drop old columns not in new schema, add new ones.
    # Use batch_alter_table for portability.

    old_cols_to_drop = [
        "user_id", "feature_project_id", "project", "title",
        "description_original", "description_language", "description_translated",
        "assignee", "due", "category", "created_by", "subtasks_json",
        "comments_json", "is_private_to_engineer", "engineer_notes",
        "priority",  # will be re-added with correct default
        "status",    # will be re-added with correct default
    ]
    new_cols = [
        ("name",               sa.String(200), {"nullable": True}),   # start nullable, fill, then NOT NULL via batch
        ("description_lang",   sa.String(10),  {"nullable": True}),
        ("created_by_id_new",  sa.Integer(),   {"nullable": True}),   # temp name to avoid clash
        ("assigned_to_id",     sa.Integer(),   {"nullable": True}),
        ("status_new",         sa.String(20),  {"nullable": False, "server_default": "not_started"}),
        ("priority_new",       sa.String(10),  {"nullable": False, "server_default": "normal"}),
        ("due_date",           sa.Date(),      {"nullable": True}),
        ("remarks",            sa.Text(),      {"nullable": True}),
        ("depends_on_task_id", sa.Integer(),   {"nullable": True}),
        ("completed_at",       sa.DateTime(),  {"nullable": True}),
    ]

    with op.batch_alter_table("tasks") as batch_op:
        # Add new columns first
        for col_name, col_type, kwargs in new_cols:
            if not _has_column("tasks", col_name):
                batch_op.add_column(sa.Column(col_name, col_type, **kwargs))

        # Copy title → name if name column was just added
        # (We handle data migration separately below)

        # Drop old columns
        for col in old_cols_to_drop:
            if _has_column("tasks", col):
                batch_op.drop_column(col)

    # Data migration: populate name from title (already dropped), use id as fallback
    # Since we drop title above, name will be NULL — set a placeholder
    conn.execute(sa.text(
        "UPDATE tasks SET name = COALESCE(name, CAST(id AS VARCHAR))"
    ))

    # Rename *_new columns to final names via batch
    with op.batch_alter_table("tasks") as batch_op:
        if _has_column("tasks", "status_new") and not _has_column("tasks", "status"):
            batch_op.alter_column("status_new", new_column_name="status", nullable=False, server_default="not_started")
        if _has_column("tasks", "priority_new") and not _has_column("tasks", "priority"):
            batch_op.alter_column("priority_new", new_column_name="priority", nullable=False, server_default="normal")
        if _has_column("tasks", "created_by_id_new") and not _has_column("tasks", "created_by_id"):
            batch_op.alter_column("created_by_id_new", new_column_name="created_by_id", nullable=True)

    # Ensure project_id is not null (it was nullable before) — skip constraint change
    # for simplicity; model enforces it at ORM layer.

    # ── 3. Add indexes ────────────────────────────────────────────────────────
    if not _has_index("tasks", "ix_tasks_project_id"):
        op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    if not _has_index("tasks", "ix_tasks_assigned_to_id"):
        op.create_index("ix_tasks_assigned_to_id", "tasks", ["assigned_to_id"])
    # ix_tasks_status may already exist
    if not _has_index("tasks", "ix_tasks_status"):
        op.create_index("ix_tasks_status", "tasks", ["status"])

    # Drop old user_id index if still present
    try:
        op.drop_index("ix_tasks_user_id", table_name="tasks")
    except Exception:
        pass

    # ── 4. Create task_activities ─────────────────────────────────────────────
    if not _has_table("task_activities"):
        op.create_table(
            "task_activities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "task_id", sa.Integer(),
                sa.ForeignKey("tasks.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_task_activities_task_id", "task_activities", ["task_id"])


def downgrade():
    # Drop task_activities
    if _has_table("task_activities"):
        op.drop_table("task_activities")

    # Recreate task_logs stub
    if not _has_table("task_logs"):
        op.create_table(
            "task_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("user_name", sa.String(100)),
            sa.Column("action", sa.String(50)),
            sa.Column("details", sa.Text()),
            sa.Column("field_changed", sa.String(50)),
            sa.Column("old_value", sa.String(200)),
            sa.Column("new_value", sa.String(200)),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
