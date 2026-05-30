from datetime import datetime
import json

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()

PASSWORD_HASH_METHOD = "pbkdf2:sha256"
PASSWORD_HASH_SALT_LENGTH = 16
PASSWORD_HASH_PREFIXES = ("pbkdf2:", "$2b$", "$2a$", "scrypt:")


def password_hash_looks_valid(value):
    if not value:
        return False
    return any(str(value).startswith(prefix) for prefix in PASSWORD_HASH_PREFIXES)


def hash_password_value(password):
    password = str(password or "")
    if not password:
        raise ValueError("Password cannot be empty.")
    return generate_password_hash(
        password,
        method=PASSWORD_HASH_METHOD,
        salt_length=PASSWORD_HASH_SALT_LENGTH,
    )


def _as_float(value):
    return float(value) if value is not None else 0.0


def _format_date(value):
    return value.strftime("%d %b %Y") if value else ""


def _load_json_list(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


# Access-control roles (used by role_required decorator and registration form)
ROLE_PROJECT_MANAGER = "project_manager"
ROLE_SITE_ENGINEER = "site_engineer"

# Job-title options (professional designations, stored in User.job_title)
USER_ROLE_OPTIONS = [
    "Site Engineer",
    "Quantity Surveyor",
    "MEP Engineer",
    "HSE Officer",
    "Procurement Officer",
    "Document Controller",
    "Subcontractor",
    "Client Representative",
    "Consultant",
]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(100), nullable=False, default="User")
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    company = db.Column(db.String(100), default="")
    # job_title: professional designation (e.g. "MEP Engineer", "Site Engineer")
    job_title = db.Column(db.String(50), default="")
    # role: access-control level — 'project_manager' or 'site_engineer'
    role = db.Column(db.String(20), nullable=False, default=ROLE_PROJECT_MANAGER)
    password_hash = db.Column(db.String(256), nullable=False)
    is_guest = db.Column(db.Boolean, default=False)
    preferred_lang = db.Column(db.String(5), default="en")
    # Geographic / billing context
    country = db.Column(db.String(10), nullable=True, default="IN")  # ISO 3166-1 alpha-2 + 'OTHER'
    preferred_currency = db.Column(db.String(3), nullable=True, default="INR")
    # Optional GSTIN for B2B India invoices
    gstin = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Security: session invalidation token — rotated on "sign out everywhere"
    session_token = db.Column(db.String(64), nullable=True, default="")
    # Security: track when password was last changed
    password_updated_at = db.Column(db.DateTime, nullable=True)

    dprs = db.relationship("DPR", backref="author", lazy=True, cascade="all, delete-orphan")
    boqs = db.relationship("BOQ", foreign_keys="BOQ.user_id", backref="author", lazy=True, cascade="all, delete-orphan")
    projects = db.relationship("Project", back_populates="user", lazy=True, cascade="all, delete-orphan")
    feature_projects = db.relationship("FeatureProject", backref="owner", lazy=True, cascade="all, delete-orphan")
    inventory_items = db.relationship("InventoryItem", backref="owner", lazy=True, cascade="all, delete-orphan")
    created_tasks = db.relationship(
        "Task",
        foreign_keys="Task.created_by_id",
        lazy=True,
    )
    assigned_tasks = db.relationship(
        "Task",
        foreign_keys="Task.assigned_to_id",
        lazy=True,
    )
    project_assignments = db.relationship(
        "ProjectAssignment",
        back_populates="user",
        foreign_keys="[ProjectAssignment.user_id]",
        lazy=True,
    )

    @property
    def password(self):
        raise AttributeError("Password is write-only.")

    @password.setter
    def password(self, password):
        self.password_hash = hash_password_value(password)

    @validates("password_hash")
    def validate_password_hash(self, key, value):
        if password_hash_looks_valid(value):
            return value
        return hash_password_value(value)

    def set_password(self, password):
        self.password_hash = hash_password_value(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def name(self):
        return self.full_name

    @name.setter
    def name(self, value):
        self.full_name = (value or "").strip() or "User"


class Plan(db.Model):
    __tablename__ = "plan"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    # monthly_price / annual_price are the SAR base prices (legacy columns, kept intact)
    monthly_price = db.Column(db.Numeric(10, 2), nullable=True)
    annual_price = db.Column(db.Numeric(10, 2), nullable=True)
    # Native INR prices (India launch primary market)
    price_inr = db.Column(db.Numeric(10, 2), nullable=True)
    price_inr_annual = db.Column(db.Numeric(10, 2), nullable=True)
    # Native USD prices (international / future)
    price_usd = db.Column(db.Numeric(10, 2), nullable=True)
    # Default currency for display (INR for India launch)
    default_currency = db.Column(db.String(3), default="INR")
    max_users = db.Column(db.Integer, nullable=True)
    max_ai_queries = db.Column(db.Integer, nullable=True)
    features = db.Column(db.Text, default="[]")

    @property
    def features_list(self):
        # Keep plan displays limited to supported features without needing a data migration.
        supported_features = {
            "DPR",
            "BOQ",
            "Inventory",
            "Tasks",
            "Translator",
            "Priority Support",
            "Dedicated Onboarding",
            "Custom Integrations",
            "SLA",
            "All Features",
        }
        return [
            feature
            for feature in _load_json_list(self.features)
            if feature in supported_features
        ]

    def get_price(self, currency="INR", billing_cycle="monthly"):
        """Return native price for currency + billing_cycle.
        Falls back to SAR-based rate conversion if no native price set."""
        currency = (currency or "INR").upper()
        if currency == "INR":
            if billing_cycle == "annual" and self.price_inr_annual is not None:
                return float(self.price_inr_annual)
            if self.price_inr is not None:
                return float(self.price_inr)
        if currency == "SAR":
            return float(
                self.annual_price if billing_cycle == "annual" else self.monthly_price or 0
            )
        if currency == "USD" and self.price_usd is not None:
            return float(self.price_usd)
        # Fallback: return monthly_price (SAR) — callers can convert
        return float(self.monthly_price or 0)

    def get_formatted_price(self, currency="INR", billing_cycle="monthly"):
        price = self.get_price(currency, billing_cycle)
        if not price:
            return "Custom"
        symbols = {"INR": "₹", "SAR": "SAR ", "USD": "$"}
        symbol = symbols.get(currency.upper(), "")
        return f"{symbol}{int(price):,}"

    def price_for_cycle(self, billing_cycle):
        """Legacy — returns SAR price for billing cycle."""
        return self.annual_price if billing_cycle == "annual" else self.monthly_price


class Subscription(db.Model):
    __tablename__ = "subscription"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"))
    billing_cycle = db.Column(db.String(10), default="monthly")
    status = db.Column(db.String(20), default="trialing")
    trial_start = db.Column(db.DateTime)
    trial_end = db.Column(db.DateTime)
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    gateway_customer_id = db.Column(db.String(100), nullable=True)
    gateway_subscription_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Trial-ending reminder flags — prevents duplicate emails
    reminder_3d_sent = db.Column(db.Boolean, default=False, nullable=False)
    reminder_1d_sent = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", backref=db.backref("subscription", uselist=False))
    plan = db.relationship("Plan")


class Invoice(db.Model):
    __tablename__ = "invoice"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"))
    invoice_number = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Numeric(10, 2))
    vat_amount = db.Column(db.Numeric(10, 2))
    total_amount = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(5), default="INR")
    buyer_gstin = db.Column(db.String(20), nullable=True)  # B2B India: buyer's GSTIN
    status = db.Column(db.String(20), default="pending")
    due_date = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    next_retry_at = db.Column(db.DateTime, nullable=True)
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="invoices")
    subscription = db.relationship("Subscription", backref="invoices")


class PaymentMethod(db.Model):
    __tablename__ = "payment_method"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    card_last_four = db.Column(db.String(4))
    card_brand = db.Column(db.String(20))
    expiry_month = db.Column(db.Integer)
    expiry_year = db.Column(db.Integer)
    is_default = db.Column(db.Boolean, default=True)
    gateway_token = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="payment_methods")


class AIQueryLog(db.Model):
    __tablename__ = "ai_query_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    feature = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="ai_query_logs")


class DPR(db.Model):
    __tablename__ = "dprs"
    __table_args__ = (db.Index("ix_dprs_user_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    feature_project_id = db.Column(db.Integer, db.ForeignKey("feature_projects.id"), nullable=True)
    date = db.Column(db.Date)
    project = db.Column(db.String(200))
    zone = db.Column(db.String(100))
    weather = db.Column(db.String(50))
    temperature = db.Column(db.String(20))
    progress_notes = db.Column(db.Text)
    issues = db.Column(db.Text)
    status = db.Column(db.String(30), default="Completed")
    workers_json = db.Column(db.Text, default="[]")
    ai_summary = db.Column(db.Text)
    ai_summary_ar = db.Column(db.Text)
    ai_key_insight = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def workers(self):
        try:
            return json.loads(self.workers_json or "[]")
        except Exception:
            return []

    @workers.setter
    def workers(self, value):
        self.workers_json = json.dumps(value)

    def to_dict(self):
        workers = self.workers
        return {
            "id": self.id,
            "date": _format_date(self.date),
            "project": self.project,
            "zone": self.zone,
            "weather": self.weather,
            "temperature": self.temperature,
            "progress_notes": self.progress_notes,
            "notes": self.progress_notes,
            "issues": self.issues,
            "status": self.status,
            "workers": len([w for w in workers if w.get("present", True)]),
            "workers_data": workers,
            "has_ai_summary": bool((self.ai_summary or "").strip()),
            "ai_summary": self.ai_summary,
            "ai_summary_ar": self.ai_summary_ar,
            "ai_key_insight": self.ai_key_insight,
            "project_id": self.project_id,
            "feature_project_id": self.feature_project_id,
            "created_at": self.created_at.strftime("%d %b %Y") if self.created_at else "",
        }


class BOQ(db.Model):
    __tablename__ = "boqs"
    __table_args__ = (db.Index("ix_boqs_user_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    feature_project_id = db.Column(db.Integer, db.ForeignKey("feature_projects.id"), nullable=True)
    parent_boq_id = db.Column(db.Integer, db.ForeignKey("boqs.id"), nullable=True)
    title = db.Column(db.String(200), default="Untitled BOQ")
    project = db.Column(db.String(200))
    status = db.Column(db.String(30), default="Draft")
    items_json = db.Column(db.Text, default="[]")
    subtotal = db.Column(db.Numeric(12, 2), default=0)
    vat_amount = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), default=0)
    ai_summary = db.Column(db.Text)
    ai_suggestions = db.Column(db.Text)
    source = db.Column(db.String(30), default="manual")
    generation_mode = db.Column(db.String(30), default="manual")
    project_description = db.Column(db.Text)
    audit_score = db.Column(db.Integer)
    audit_results_json = db.Column(db.Text)
    audit_generated_at = db.Column(db.DateTime)
    project_type = db.Column(db.String(80))
    floor_area_sqm = db.Column(db.Float)
    is_master = db.Column(db.Boolean, default=False)
    distributed_at = db.Column(db.DateTime)
    # BOQ rebuild Phase 5: distribution + versioning columns
    parent_master_boq_id = db.Column(db.Integer, db.ForeignKey('boqs.id', ondelete='SET NULL'), nullable=True)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    trade_section = db.Column(db.String(50), nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False, server_default='1')
    parent_revision_id = db.Column(db.Integer, db.ForeignKey('boqs.id', ondelete='SET NULL'), nullable=True)
    design_files_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent_boq = db.relationship(
        "BOQ",
        foreign_keys=[parent_boq_id],
        remote_side=[id],
        backref=db.backref("child_versions", lazy=True),
    )
    # New rebuild relationships (no backref to avoid conflicts)
    assigned_engineer = db.relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
        lazy=True,
    )
    packages = db.relationship("BOQPackage", backref="boq", lazy=True, cascade="all, delete-orphan")
    actuals = db.relationship("BOQActual", backref="boq", lazy=True, cascade="all, delete-orphan")

    @property
    def items(self):
        try:
            return json.loads(self.items_json or "[]")
        except Exception:
            return []

    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value)

    @property
    def audit_results(self):
        try:
            parsed = json.loads(self.audit_results_json or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "project": self.project,
            "status": self.status,
            "items": self.items,
            "subtotal": _as_float(self.subtotal),
            "vat_amount": _as_float(self.vat_amount),
            "grand_total": _as_float(self.grand_total),
            "ai_summary": self.ai_summary,
            "source": self.source,
            "generation_mode": self.generation_mode or self.source or "manual",
            "project_description": self.project_description or "",
            "audit_score": self.audit_score,
            "audit_results": self.audit_results,
            "audit_generated_at": _format_date(self.audit_generated_at),
            "project_type": self.project_type or "",
            "floor_area_sqm": _as_float(self.floor_area_sqm),
            "parent_boq_id": self.parent_boq_id,
            "is_master": bool(self.is_master),
            "distributed_at": _format_date(self.distributed_at),
            "project_id": self.project_id,
            "feature_project_id": self.feature_project_id,
            "created_at": self.created_at.strftime("%d %b %Y") if self.created_at else "",
            "last_modified": self.updated_at.strftime("%d %b %Y") if self.updated_at else "",
            "total": _as_float(self.grand_total),
        }


class BOQPackage(db.Model):
    __tablename__ = "boq_packages"
    __table_args__ = (db.Index("ix_boq_packages_boq_id", "boq_id"),)

    id = db.Column(db.Integer, primary_key=True)
    boq_id = db.Column(db.Integer, db.ForeignKey("boqs.id"), nullable=False)
    package_name = db.Column(db.String(200), nullable=False)
    package_type = db.Column(db.String(40), default="provisional")
    assigned_engineer_name = db.Column(db.String(120), nullable=False)
    assigned_engineer_email = db.Column(db.String(160), nullable=True)
    items_json = db.Column(db.Text, default="[]")
    subtotal_sar = db.Column(db.Float, default=0.0)
    vat_amount_sar = db.Column(db.Float, default=0.0)
    grand_total_sar = db.Column(db.Float, default=0.0)
    completion_percentage = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(30), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actuals = db.relationship("BOQActual", backref="package", lazy=True)

    @property
    def items(self):
        try:
            parsed = json.loads(self.items_json or "[]")
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value)

    def to_dict(self):
        return {
            "id": self.id,
            "boq_id": self.boq_id,
            "package_name": self.package_name,
            "package_type": self.package_type,
            "assigned_engineer_name": self.assigned_engineer_name,
            "assigned_engineer_email": self.assigned_engineer_email,
            "items": self.items,
            "subtotal_sar": _as_float(self.subtotal_sar),
            "vat_amount_sar": _as_float(self.vat_amount_sar),
            "grand_total_sar": _as_float(self.grand_total_sar),
            "completion_percentage": _as_float(self.completion_percentage),
            "status": self.status,
            "created_at": _format_date(self.created_at),
        }


class BOQActual(db.Model):
    __tablename__ = "boq_actuals"
    __table_args__ = (
        db.Index("ix_boq_actuals_boq_id", "boq_id"),
        db.Index("ix_boq_actuals_package_id", "package_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    boq_id = db.Column(db.Integer, db.ForeignKey("boqs.id"), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey("boq_packages.id"), nullable=True)
    item_no = db.Column(db.String(40), nullable=False)
    item_description = db.Column(db.String(600))
    budgeted_qty = db.Column(db.Float, default=0.0)
    actual_qty_used = db.Column(db.Float, default=0.0)
    budgeted_rate_sar = db.Column(db.Float, default=0.0)
    actual_rate_sar = db.Column(db.Float, nullable=True)
    budgeted_total_sar = db.Column(db.Float, default=0.0)
    actual_total_sar = db.Column(db.Float, default=0.0)
    variance_sar = db.Column(db.Float, default=0.0)
    variance_percentage = db.Column(db.Float, default=0.0)
    source = db.Column(db.String(30))
    source_id = db.Column(db.Integer, nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorded_by = db.Column(db.String(120))

    def to_dict(self):
        return {
            "id": self.id,
            "boq_id": self.boq_id,
            "package_id": self.package_id,
            "item_no": self.item_no,
            "item_description": self.item_description,
            "budgeted_qty": _as_float(self.budgeted_qty),
            "actual_qty_used": _as_float(self.actual_qty_used),
            "budgeted_rate_sar": _as_float(self.budgeted_rate_sar),
            "actual_rate_sar": _as_float(self.actual_rate_sar),
            "budgeted_total_sar": _as_float(self.budgeted_total_sar),
            "actual_total_sar": _as_float(self.actual_total_sar),
            "variance_sar": _as_float(self.variance_sar),
            "variance_percentage": _as_float(self.variance_percentage),
            "source": self.source,
            "source_id": self.source_id,
            "recorded_at": self.recorded_at.strftime("%d %b %Y %H:%M") if self.recorded_at else "",
            "recorded_by": self.recorded_by,
        }


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(200), nullable=False)
    reference_number = db.Column(db.String(100))
    project_code = db.Column(db.String(20), unique=True)

    client_name = db.Column(db.String(200))
    client_contact = db.Column(db.String(200))

    contract_value = db.Column(db.Numeric(15, 2))
    currency = db.Column(db.String(5), default="SAR")

    start_date = db.Column(db.Date)
    planned_completion = db.Column(db.Date)
    actual_completion = db.Column(db.Date, nullable=True)

    location_city = db.Column(db.String(100))
    location_zone = db.Column(db.String(100))
    project_type = db.Column(db.String(50))

    lead_engineer = db.Column(db.String(200))
    project_manager = db.Column(db.String(200))

    status = db.Column(db.String(20), default="active")
    color = db.Column(db.String(10), default="#0A1628")

    health_score = db.Column(db.Integer, default=100)
    health_status = db.Column(db.String(10), default="green")
    health_summary = db.Column(db.Text)
    health_components_json = db.Column(db.Text, default="{}")
    health_last_calculated = db.Column(db.DateTime)

    completion_summary = db.Column(db.Text, nullable=True)
    completion_summary_ar = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="projects")
    dprs = db.relationship("DPR", backref="dna_project", lazy=True)
    boqs = db.relationship("BOQ", backref="dna_project", lazy=True)
    inventory_items = db.relationship("InventoryItem", backref="project", lazy=True)
    tasks = db.relationship("Task", backref="project_record", lazy=True)
    milestones = db.relationship("ProjectMilestone", back_populates="project", lazy=True, cascade="all, delete-orphan", order_by="ProjectMilestone.planned_date")
    packages = db.relationship("EngineerPackage", back_populates="project", lazy=True, cascade="all, delete-orphan")
    assignments = db.relationship("ProjectAssignment", back_populates="project", cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        try:
            health_components = json.loads(self.health_components_json or "{}")
        except Exception:
            health_components = {}
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "reference_number": self.reference_number,
            "project_code": self.project_code,
            "client_name": self.client_name,
            "client_contact": self.client_contact,
            "contract_value": _as_float(self.contract_value),
            "currency": self.currency or "SAR",
            "start_date": _format_date(self.start_date),
            "planned_completion": _format_date(self.planned_completion),
            "actual_completion": _format_date(self.actual_completion),
            "location_city": self.location_city,
            "location_zone": self.location_zone,
            "project_type": self.project_type,
            "lead_engineer": self.lead_engineer,
            "project_manager": self.project_manager,
            "status": self.status,
            "color": self.color,
            "health_score": self.health_score,
            "health_status": self.health_status,
            "health_summary": self.health_summary,
            "health_components": health_components,
            "health_last_calculated": _format_date(self.health_last_calculated),
            "created_at": _format_date(self.created_at),
        }


class ProjectMilestone(db.Model):
    __tablename__ = "project_milestone"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(200))
    planned_date = db.Column(db.Date)
    actual_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="pending")

    project = db.relationship("Project", back_populates="milestones")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "planned_date": _format_date(self.planned_date),
            "actual_date": _format_date(self.actual_date),
            "status": self.status,
        }


class EngineerPackage(db.Model):
    __tablename__ = "engineer_package"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    boq_id = db.Column(db.Integer, db.ForeignKey("boqs.id"), nullable=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_engineer_name = db.Column(db.String(200))
    trade = db.Column(db.String(50))
    package_value = db.Column(db.Numeric(15, 2))
    scope_description = db.Column(db.Text)
    completion_percentage = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")
    item_statuses_json = db.Column(db.Text, default="{}")
    notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="packages")
    boq = db.relationship("BOQ", backref="engineer_packages")
    assigned_user = db.relationship("User", backref="engineer_packages", foreign_keys=[assigned_user_id])

    @property
    def item_statuses(self):
        try:
            parsed = json.loads(self.item_statuses_json or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @item_statuses.setter
    def item_statuses(self, value):
        self.item_statuses_json = json.dumps(value or {})

    def update_item_status(self, item_index, new_status):
        """Update status for a single BOQ item and recalculate completion_percentage."""
        valid_statuses = ['not_started', 'in_progress', 'complete']
        if new_status not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        statuses = self.item_statuses
        statuses[str(item_index)] = new_status
        self.item_statuses = statuses
        # Calculate total items from linked BOQ
        total_items = 0
        if self.boq_id:
            try:
                boq = db.session.get(BOQ, self.boq_id)
                if boq:
                    total_items = len(boq.items)
            except Exception:
                pass
        if total_items > 0:
            completed_count = sum(1 for s in statuses.values() if s == 'complete')
            self.completion_percentage = round((completed_count / total_items) * 100, 1)
            if completed_count == total_items:
                self.status = 'completed'
            elif self.status == 'completed':
                self.status = 'active'

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "boq_id": self.boq_id,
            "assigned_user_id": self.assigned_user_id,
            "assigned_engineer_name": self.assigned_engineer_name,
            "trade": self.trade,
            "package_value": _as_float(self.package_value),
            "scope_description": self.scope_description,
            "completion_percentage": _as_float(self.completion_percentage),
            "status": self.status,
            "notified_at": _format_date(self.notified_at),
            "created_at": _format_date(self.created_at),
        }


class InventoryAssignment(db.Model):
    __tablename__ = 'inventory_assignments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id', ondelete='CASCADE'), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    allocated_qty = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(20), default='allocated')  # allocated | in_use | depleted | returned
    notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('project_id', 'inventory_item_id', 'assigned_user_id', name='uq_inv_assignment'),
    )

    project = db.relationship('Project', backref=db.backref('inventory_assignments', lazy=True))
    inventory_item = db.relationship('InventoryItem', backref=db.backref('assignments', lazy=True))
    assigned_user = db.relationship('User', backref=db.backref('inventory_assignments', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'inventory_item_id': self.inventory_item_id,
            'assigned_user_id': self.assigned_user_id,
            'allocated_qty': _as_float(self.allocated_qty),
            'status': self.status,
            'notified_at': _format_date(self.notified_at),
            'created_at': _format_date(self.created_at),
        }


class Notification(db.Model):
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    message = db.Column(db.Text)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="notifications")

    def to_dict(self):
        message = self.message or ""
        message_lc = message.lower()
        title = "Workspace Assignment"
        icon = "fa-folder-open"
        color = "primary"

        if any(word in message_lc for word in ("low stock", "critical stock", "inventory", "allocated")):
            title = "Inventory Update"
            icon = "fa-boxes-stacked"
            color = "warning"
        if any(word in message_lc for word in ("requests inventory", "stock request", "request inventory")):
            title = "Stock Request"
            icon = "fa-triangle-exclamation"
            color = "danger"
        elif any(word in message_lc for word in ("boq", "quantity", "revision", "package")):
            title = "BOQ Update"
            icon = "fa-file-invoice"
            color = "primary"
        elif "task" in message_lc:
            title = "Task Assignment"
            icon = "fa-list-check"
            color = "success"
        elif "project" in message_lc:
            title = "Project Update"
            icon = "fa-diagram-project"
            color = "primary"

        return {
            "id": f"db-{self.id}",
            "type": "assignment",
            "icon": icon,
            "color": color,
            "title": title,
            "message": message,
            "time": self.created_at.strftime("%d %b %Y %H:%M") if self.created_at else "",
            "link": self.link or "/workspace",
            "read": bool(self.is_read),
        }


class FeatureProject(db.Model):
    __tablename__ = "feature_projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    color = db.Column(db.String(10), default="#0A1628")
    feature = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", "feature", name="unique_project_per_feature"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "feature": self.feature,
        }


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"
    __table_args__ = (db.Index("ix_inventory_items_user_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    feature_project_id = db.Column(db.Integer, db.ForeignKey("feature_projects.id"), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    name_hi = db.Column(db.String(200), nullable=True)  # Hindi (Devanagari) for Indian projects
    category = db.Column(db.String(50))
    unit = db.Column(db.String(30))
    stock = db.Column(db.Numeric(12, 3), default=0)
    threshold = db.Column(db.Numeric(12, 3), default=0)
    value_sar = db.Column(db.Numeric(12, 2), default=0)
    supplier = db.Column(db.String(100))
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    # source: 'manual', 'ai_generated_master', 'bulk_upload', 'engineer_added'
    source = db.Column(db.String(30), nullable=True, default='manual')
    category_ar = db.Column(db.String(80), nullable=True)
    design_files_json = db.Column(db.Text, nullable=True)
    master_inventory_batch_id = db.Column(db.String(40), nullable=True)
    parent_batch_id = db.Column(db.String(40), nullable=True)
    # Rich procurement schema (migration 011)
    specification = db.Column(db.Text, nullable=True)
    brand_suggestions_json = db.Column(db.Text, nullable=True)
    storage_requirements = db.Column(db.Text, nullable=True)
    reorder_lead_time_days = db.Column(db.Integer, nullable=True)
    min_order_qty = db.Column(db.Numeric(12, 2), nullable=True)
    min_order_unit = db.Column(db.String(50), nullable=True)
    safety_notes = db.Column(db.Text, nullable=True)
    alternative_items_json = db.Column(db.Text, nullable=True)
    shelf_life_days = db.Column(db.Integer, nullable=True)
    shelf_life_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @hybrid_property
    def status(self):
        if self.stock == 0:
            return "critical"
        if self.stock < self.threshold:
            return "low"
        return "ok"

    @status.expression
    def status(cls):
        return case(
            (cls.stock == 0, "critical"),
            (cls.stock < cls.threshold, "low"),
            else_="ok",
        )

    @property
    def updated(self):
        if self.updated_at:
            return self.updated_at.strftime("%d %b %Y")
        return ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_ar": self.name_ar or "",
            "category": self.category,
            "unit": self.unit,
            "stock": _as_float(self.stock),
            "threshold": _as_float(self.threshold),
            "status": self.status,
            "value_sar": _as_float(self.value_sar),
            "supplier": self.supplier,
            "location": self.location,
            "notes": self.notes,
            "source": self.source or "manual",
            "project_id": self.project_id,
            "feature_project_id": self.feature_project_id,
            "updated": self.updated,
        }


class Task(db.Model):
    """Rebuilt task model — project-scoped, proper FK assignee, dependency support."""
    __tablename__ = "tasks"
    __table_args__ = (
        db.Index("ix_tasks_project_id", "project_id"),
        db.Index("ix_tasks_assigned_to_id", "assigned_to_id"),
        db.Index("ix_tasks_status", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    name = db.Column(db.String(200), nullable=False)
    name_hi = db.Column(db.String(200), nullable=True)  # Hindi name for Indian projects
    description = db.Column(db.Text, nullable=True)
    description_lang = db.Column(db.String(10), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    # not_started | in_progress | review | done
    status = db.Column(db.String(20), nullable=False, default="not_started")

    # low | normal | high | urgent
    priority = db.Column(db.String(10), nullable=False, default="normal")

    due_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    depends_on_task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    project_rel = db.relationship("Project", foreign_keys=[project_id], lazy="select")
    created_by = db.relationship("User", foreign_keys=[created_by_id], lazy="select")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], lazy="select")
    depends_on = db.relationship("Task", foreign_keys=[depends_on_task_id], remote_side="Task.id", lazy="select")
    activities = db.relationship(
        "TaskActivity", back_populates="task",
        cascade="all, delete-orphan", lazy="dynamic",
        order_by="TaskActivity.created_at",
    )

    @property
    def is_overdue(self):
        if self.due_date and self.status != "done":
            from datetime import date
            return self.due_date < date.today()
        return False

    @property
    def days_until_due(self):
        if self.due_date:
            from datetime import date
            return (self.due_date - date.today()).days
        return None


class TaskActivity(db.Model):
    """Activity feed for a task — replaces TaskLog."""
    __tablename__ = "task_activities"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # created | status_changed | assigned | reassigned | commented |
    # completed | reopened | edited
    action = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship("Task", back_populates="activities")
    actor = db.relationship("User", foreign_keys=[actor_id], lazy="select")


# Keep TaskLog as a stub so existing scripts/imports don't explode
# before migration runs — will be dropped by migration 012.
class TaskLog(db.Model):
    __tablename__ = "task_logs"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    user_name = db.Column(db.String(100))
    action = db.Column(db.String(50))
    details = db.Column(db.Text)
    field_changed = db.Column(db.String(50))
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UsageLog(db.Model):
    __tablename__ = "usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    item_id = db.Column(db.Integer)
    item_name = db.Column(db.String(200))
    quantity_used = db.Column(db.Numeric(12, 3))
    unit = db.Column(db.String(30))
    used_by = db.Column(db.String(100))
    zone = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    notes_lang = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "item_name": self.item_name,
            "quantity_used": _as_float(self.quantity_used),
            "unit": self.unit,
            "used_by": self.used_by,
            "zone": self.zone,
            "notes": self.notes or "",
            "date": self.created_at.strftime("%d %b %Y") if self.created_at else "",
        }


class StockRequest(db.Model):
    __tablename__ = "stock_requests"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.id', ondelete='SET NULL'), nullable=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    requested_qty = db.Column(db.Numeric(12, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=True)
    proposed_item_name = db.Column(db.String(200), nullable=True)
    proposed_item_name_ar = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    description_lang = db.Column(db.String(10), nullable=True)
    attached_files_json = db.Column(db.Text, nullable=True)
    # Rich request fields (migration 011)
    urgency = db.Column(db.String(20), nullable=True, default='normal')
    preferred_brand = db.Column(db.String(200), nullable=True)
    specification_requested = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    approved_qty = db.Column(db.Numeric(12, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', foreign_keys=[project_id], backref=db.backref('stock_requests', lazy=True))
    inventory_item = db.relationship('InventoryItem', foreign_keys=[inventory_item_id], lazy=True)
    requested_by = db.relationship('User', foreign_keys=[requested_by_user_id], lazy=True)
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_user_id], lazy=True)


class ProjectAssignment(db.Model):
    """Explicit engineer-to-project assignment.  One row per (project, engineer)
    pair.  Access control in projects_list and get_project_or_403 checks
    both EngineerPackage and this table so engineers see a project as soon as
    a PM assigns them, even before packages exist."""
    __tablename__ = "project_assignments"
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_on_project = db.Column(db.String(50), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="assignments")
    user = db.relationship(
        "User",
        back_populates="project_assignments",
        foreign_keys=[user_id],
    )


class ProjectCounter(db.Model):
    """One row per calendar year; last_seq is the highest sequence number
    issued for that year.  SELECT FOR UPDATE on this row makes code
    generation race-safe on PostgreSQL."""
    __tablename__ = "project_counters"

    year = db.Column(db.Integer, primary_key=True)
    last_seq = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GatewayPlan(db.Model):
    """Cached mapping from (provider, plan_code, currency, billing_cycle) →
    gateway's own plan ID.  Avoids re-creating plans on every subscription.
    """
    __tablename__ = "gateway_plans"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False)           # 'razorpay', 'stripe', etc.
    cache_key = db.Column(db.String(100), nullable=False)         # '{plan_code}_{currency}_{cycle}'
    gateway_plan_id = db.Column(db.String(100), nullable=False)   # provider's own plan ID
    plan_code = db.Column(db.String(30), nullable=False)          # BanaaIQ internal plan name
    currency = db.Column(db.String(3), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("provider", "cache_key", name="uq_gateway_plan_provider_key"),
    )
