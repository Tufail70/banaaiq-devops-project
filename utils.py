import html
import json
import time
from datetime import date, datetime

from flask import current_app, has_request_context, request, url_for
from flask_mail import Message
from sqlalchemy import extract

from models import AIQueryLog, Invoice, PaymentMethod, Project, db

# ---------------------------------------------------------------------------
# In-process health-score cache  {project_id: {'data': dict, 'expires': float}}
# ---------------------------------------------------------------------------
_health_cache: dict = {}


def get_subscription_status(user):
    if not getattr(user, "is_authenticated", False):
        return "none"
    sub = getattr(user, "subscription", None)
    if not sub:
        return "none"
    if sub.status == "trialing":
        if sub.trial_end and datetime.utcnow() < sub.trial_end:
            days_left = max((sub.trial_end - datetime.utcnow()).days, 0)
            return f"trialing:{days_left}"
        sub.status = "expired"
        db.session.commit()
        return "expired"
    return sub.status or "none"


def get_monthly_ai_usage(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return AIQueryLog.query.filter(
        AIQueryLog.user_id == user.id,
        AIQueryLog.created_at >= month_start,
    ).count()


def can_use_ai(user):
    status = get_subscription_status(user)
    if status.startswith("trialing") or status == "active":
        plan = getattr(getattr(user, "subscription", None), "plan", None)
        if not plan:
            return False, "No subscription plan is attached to your account."
        if plan.max_ai_queries is None:
            return True, None
        used = get_monthly_ai_usage(user)
        remaining = plan.max_ai_queries - used
        if remaining <= 0:
            return False, "Monthly AI limit reached. Upgrade to Professional for unlimited AI."
        return True, None
    if status in ("expired", "none"):
        return False, "Start a free trial to use AI features."
    if status == "past_due":
        return False, "Payment failed. Please update your payment method."
    if status == "cancelled":
        return False, "Subscription cancelled. Resubscribe to use AI features."
    return False, "Upgrade required."


def log_ai_query(user, feature):
    if not getattr(user, "is_authenticated", False):
        return None
    log = AIQueryLog(user_id=user.id, feature=feature)
    db.session.add(log)
    db.session.commit()
    return log


def generate_invoice_number():
    year = datetime.utcnow().year
    count = Invoice.query.filter(
        extract("year", Invoice.created_at) == year
    ).count() + 1
    return f"INV-{year}-{str(count).zfill(4)}"


def generate_project_code():
    from models import ProjectCounter
    from sqlalchemy import select

    year = datetime.utcnow().year

    counter = db.session.execute(
        select(ProjectCounter)
        .where(ProjectCounter.year == year)
        .with_for_update()
    ).scalar_one_or_none()

    if counter is None:
        counter = ProjectCounter(year=year, last_seq=1)
        db.session.add(counter)
        db.session.flush()
    else:
        counter.last_seq += 1
        db.session.flush()

    return f"BIQ-{year}-{str(counter.last_seq).zfill(4)}"


def calculate_vat(amount):
    vat = round(float(amount) * 0.15, 2)
    total = round(float(amount) + vat, 2)
    return vat, total


def _extract_component_score(value, default=80):
    """Handle both old flat-int format and new {'score': int, ...} dict format."""
    if isinstance(value, dict):
        return int(value.get("score", default) or default)
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def get_health_components(project):
    try:
        components = json.loads(getattr(project, "health_components_json", "") or "{}")
    except Exception:
        components = {}
    return {
        "schedule": _extract_component_score(components.get("schedule"), 80),
        "budget": _extract_component_score(components.get("budget"), 80),
        "task": _extract_component_score(components.get("task") or components.get("tasks"), 80),
        "inventory": _extract_component_score(components.get("inventory"), 80),
    }


def project_health_payload(project):
    score = int(project.health_score if project.health_score is not None else 100)
    status = project.health_status or "green"
    summary = project.health_summary or "All systems healthy."
    last_calculated = getattr(project, "health_last_calculated", None)
    return {
        "score": score,
        "status": status,
        "summary": summary,
        "components": get_health_components(project),
        "last_calculated": last_calculated.isoformat() if last_calculated else None,
    }


def _inventory_spend_fallback(items):
    actual = 0.0
    for item in items:
        unit_cost = getattr(item, "unit_cost", None)
        quantity = getattr(item, "quantity", None)
        if unit_cost is not None or quantity is not None:
            actual += float(unit_cost or 0) * float(quantity or 0)
        else:
            actual += float(getattr(item, "value_sar", 0) or 0)
    return actual


def calculate_health_score(project):
    """Compute a 4-component health score (0-100 each, equal 25% weight).

    Components
    ----------
    schedule  : milestone on-time rate OR time-vs-task-completion ratio
    budget    : BOQ planned vs BOQActual actual spend
    task      : tasks with status='complete' / total tasks
    inventory : penalty for critical/low stock items

    Returns the full result dict (also persists to Project columns).
    """
    from models import BOQ, BOQActual, InventoryItem, ProjectMilestone, Task

    today = date.today()

    # ── 1. SCHEDULE PERFORMANCE (0-100) ──────────────────────────────────────
    milestones = ProjectMilestone.query.filter_by(project_id=project.id).all()
    if milestones:
        on_time = sum(
            1 for m in milestones
            if m.actual_date and m.planned_date and m.actual_date <= m.planned_date
        )
        sched_score = int(on_time / len(milestones) * 100) if milestones else 80
        sched_detail = f"{on_time}/{len(milestones)} milestones on time"
        sched_detail_ar = f"{on_time}/{len(milestones)} معالم في الوقت المحدد"
    else:
        start = project.start_date
        end = project.planned_completion
        if start and end and end > start:
            total_days = max((end - start).days, 1)
            elapsed_days = max((today - start).days, 0)
            time_elapsed_ratio = min(elapsed_days / total_days, 1.0)
            all_tasks = Task.query.filter_by(project_id=project.id).all()
            total_tasks_sched = len(all_tasks)
            done_tasks_sched = sum(1 for t in all_tasks if t.status == "complete")
            task_completion_ratio = done_tasks_sched / total_tasks_sched if total_tasks_sched else 0.0
            if time_elapsed_ratio <= 0:
                sched_score = 100
            elif task_completion_ratio >= time_elapsed_ratio:
                sched_score = 100
            else:
                sched_score = max(0, int(task_completion_ratio / time_elapsed_ratio * 100))
            sched_detail = f"{int(time_elapsed_ratio*100)}% time elapsed, {int(task_completion_ratio*100)}% tasks complete"
            sched_detail_ar = f"{int(time_elapsed_ratio*100)}% من الوقت مضى، {int(task_completion_ratio*100)}% من المهام مكتملة"
        else:
            sched_score = 80
            sched_detail = "Timeline not fully set"
            sched_detail_ar = "الجدول الزمني غير مكتمل"

    # ── 2. BUDGET PERFORMANCE (0-100) ─────────────────────────────────────────
    boqs = BOQ.query.filter_by(project_id=project.id).all()
    budgeted = sum(float(b.grand_total or 0) for b in boqs)
    if not boqs or budgeted == 0:
        budget_score = 80
        budget_detail = "No BOQ defined"
        budget_detail_ar = "لا يوجد جدول كميات"
    else:
        boq_ids = [b.id for b in boqs]
        actual_rows = BOQActual.query.filter(BOQActual.boq_id.in_(boq_ids)).all() if boq_ids else []
        actual = sum(float(r.actual_total_sar or 0) for r in actual_rows)
        if actual <= budgeted:
            budget_score = 100
            budget_detail = f"Spend SAR {actual:,.0f} within budget SAR {budgeted:,.0f}"
            budget_detail_ar = f"الإنفاق SAR {actual:,.0f} ضمن الميزانية SAR {budgeted:,.0f}"
        else:
            over_pct = ((actual - budgeted) / budgeted) * 100
            budget_score = max(0, 100 - int(over_pct))
            budget_detail = f"Over budget by {over_pct:.1f}%"
            budget_detail_ar = f"تجاوز الميزانية بنسبة {over_pct:.1f}%"

    # ── 3. TASK COMPLETION (0-100) ────────────────────────────────────────────
    all_tasks = Task.query.filter_by(project_id=project.id).all()
    total_tasks = len(all_tasks)
    done_tasks = sum(1 for t in all_tasks if t.status == "complete")
    if total_tasks == 0:
        task_score = 80
        task_detail = "No tasks created"
        task_detail_ar = "لا توجد مهام"
    else:
        task_score = int(done_tasks / total_tasks * 100)
        task_detail = f"{done_tasks}/{total_tasks} tasks complete"
        task_detail_ar = f"{done_tasks}/{total_tasks} مهام مكتملة"

    # ── 4. INVENTORY HEALTH (0-100) ───────────────────────────────────────────
    inventory_items = InventoryItem.query.filter_by(project_id=project.id).all()
    if not inventory_items:
        inv_score = 100
        inv_detail = "No inventory items"
        inv_detail_ar = "لا يوجد مخزون"
    else:
        critical_count = 0
        low_count = 0
        for item in inventory_items:
            stock = float(item.stock or 0)
            threshold = float(item.threshold or 0)
            if stock < threshold * 0.25:
                critical_count += 1
            elif stock < threshold:
                low_count += 1
        inv_score = max(0, min(100, 100 - (critical_count * 15) - (low_count * 5)))
        if critical_count:
            inv_detail = f"{critical_count} critical, {low_count} low stock items"
            inv_detail_ar = f"{critical_count} حرج، {low_count} منخفض في المخزون"
        elif low_count:
            inv_detail = f"{low_count} low stock items"
            inv_detail_ar = f"{low_count} عناصر مخزون منخفضة"
        else:
            inv_detail = "All stock levels healthy"
            inv_detail_ar = "مستويات المخزون جيدة"

    # ── FINAL SCORE ───────────────────────────────────────────────────────────
    final_score = round(0.25 * sched_score + 0.25 * budget_score + 0.25 * task_score + 0.25 * inv_score)

    if final_score >= 75:
        status = "green"
        status_key = "on_track"
    elif final_score >= 50:
        status = "amber"
        status_key = "at_risk"
    else:
        status = "red"
        status_key = "critical"

    # Find weakest component for summary
    component_scores = {
        "schedule": sched_score,
        "budget": budget_score,
        "task": task_score,
        "inventory": inv_score,
    }
    weakest = min(component_scores, key=component_scores.get)
    weakest_labels = {
        "schedule": ("schedule performance", "الأداء الزمني"),
        "budget": ("budget performance", "أداء الميزانية"),
        "task": ("task completion", "إتمام المهام"),
        "inventory": ("inventory health", "صحة المخزون"),
    }
    wl_en, wl_ar = weakest_labels[weakest]
    summary_en = f"Project health is {status_key.replace('_', ' ')}; weakest area is {wl_en}."
    _status_ar_map = {'on_track': 'على المسار', 'at_risk': 'في خطر', 'critical': 'حرجة'}
    _status_ar = _status_ar_map.get(status_key, status_key)
    summary_ar = f"صحة المشروع {_status_ar}؛ أضعف مجال هو {wl_ar}."

    components = {
        "schedule": {"score": sched_score, "detail": sched_detail, "detail_ar": sched_detail_ar},
        "budget": {"score": budget_score, "detail": budget_detail, "detail_ar": budget_detail_ar},
        "task": {"score": task_score, "detail": task_detail, "detail_ar": task_detail_ar},
        "inventory": {"score": inv_score, "detail": inv_detail, "detail_ar": inv_detail_ar},
    }

    now = datetime.utcnow()
    project.health_score = final_score
    project.health_status = status
    project.health_summary = summary_en
    project.health_components_json = json.dumps(components)
    project.health_last_calculated = now
    db.session.commit()

    result = {
        "score": final_score,
        "status": status,
        "status_key": status_key,
        "summary": summary_en,
        "summary_ar": summary_ar,
        "components": components,
        "last_calculated": now.isoformat(),
    }
    return result


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
_HEALTH_CACHE_TTL = 300  # seconds


def get_cached_health_score(project_id):
    """Return cached health dict or compute fresh and cache it."""
    now = time.time()
    cached = _health_cache.get(project_id)
    if cached and cached["expires"] > now:
        return cached["data"]
    # Cache miss or expired — load project and recompute
    project = db.session.get(Project, project_id)
    if not project:
        return None
    data = calculate_health_score(project)
    _health_cache[project_id] = {"data": data, "expires": now + _HEALTH_CACHE_TTL}
    return data


def invalidate_health_cache(project_id):
    """Remove project from in-process cache so next read recomputes."""
    _health_cache.pop(project_id, None)


def _app_base_url():
    configured = (current_app.config.get("APP_BASE_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    if has_request_context():
        return request.url_root.rstrip("/")
    return "https://banaaiq.com"


def _absolute_url(endpoint, **values):
    if has_request_context():
        return url_for(endpoint, _external=True, **values)
    return f"{_app_base_url()}{url_for(endpoint, **values)}"


def _plain_text(value):
    return html.unescape(str(value or "")).replace("<br>", "\n")


def _send_billing_email(user, subject, preheader, title, body_html, cta_text=None, cta_url=None):
    if not getattr(user, "email", None):
        current_app.logger.warning("Billing email skipped because user has no email address.")
        return False

    html_body = f"""
<div style="font-family:Arial,sans-serif;background:#f5f6fa;padding:24px 12px;">
  <div style="max-width:620px;margin:0 auto;background:#ffffff;border:1px solid #e4e6eb;border-radius:12px;overflow:hidden;">
    <div style="background:#0a1628;padding:22px 28px;">
      <div style="color:#d4af37;font-size:26px;font-weight:700;letter-spacing:0.02em;">BanaaIQ</div>
      <div style="color:rgba(255,255,255,0.72);font-size:12px;margin-top:6px;">{html.escape(preheader)}</div>
    </div>
    <div style="padding:28px;">
      <h2 style="margin:0 0 16px;color:#0a1628;font-size:24px;">{html.escape(title)}</h2>
      <div style="color:#2f3542;font-size:15px;line-height:1.75;">{body_html}</div>
      {f'<div style="margin-top:24px;"><a href="{html.escape(cta_url)}" style="display:inline-block;background:#d4af37;color:#0a1628;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:8px;">{html.escape(cta_text)}</a></div>' if cta_text and cta_url else ''}
    </div>
    <div style="padding:18px 28px;border-top:1px solid #eceef3;color:#7b8190;font-size:12px;">
      BanaaIQ &middot; iqbaana@gmail.com
    </div>
  </div>
</div>
    """.strip()

    msg = Message(
        subject=subject,
        recipients=[user.email],
        html=html_body,
        body=_plain_text(preheader),
    )

    try:
        mailer = current_app.extensions.get("mail")
        if not mailer:
            raise RuntimeError("Flask-Mail extension is not initialized.")
        mailer.send(msg)
        return True
    except Exception as error:
        current_app.logger.error("Billing email send error: %s", error)
        return False


def send_trial_welcome_email(user, plan_name, trial_end):
    dashboard_url = _absolute_url("dashboard_overview")
    trial_end_text = trial_end.strftime("%d %B %Y")
    body_html = (
        f"<p>Welcome to BanaaIQ. Your <strong>{html.escape(plan_name)}</strong> trial is now active.</p>"
        f"<p>Your trial includes access to the plan features until <strong>{html.escape(trial_end_text)}</strong>.</p>"
        "<p>You can now create DPRs, manage BOQs, track inventory, coordinate tasks, and use the AI workflows included in your plan.</p>"
        "<p>Open your dashboard to get started.</p>"
    )
    return _send_billing_email(
        user,
        subject=f"Your BanaaIQ {plan_name} Trial Has Started 🎉",
        preheader="Your trial is live and ready to use.",
        title="Your Trial Has Started",
        body_html=body_html,
        cta_text="Open Dashboard",
        cta_url=dashboard_url,
    )


def send_trial_expiry_warning_email(user, days_remaining):
    pricing_url = _absolute_url("pricing")
    body_html = (
        f"<p>Your BanaaIQ trial ends in <strong>{int(days_remaining)} days</strong>.</p>"
        "<p>Choose a plan to keep using DPR, BOQ, inventory, translator, and assistant workflows without interruption.</p>"
    )
    return _send_billing_email(
        user,
        subject=f"Your BanaaIQ Trial Ends in {int(days_remaining)} Days",
        preheader="Keep your team moving by choosing a plan before your trial ends.",
        title="Trial Ending Soon",
        body_html=body_html,
        cta_text="View Plans",
        cta_url=pricing_url,
    )


def send_payment_retry_email(user, invoice, next_retry_date):
    billing_url = _absolute_url("billing")
    payment_method = PaymentMethod.query.filter_by(user_id=user.id, is_default=True).first()
    last4 = payment_method.card_last_four if payment_method else "----"
    body_html = (
        "<p>We could not process your latest BanaaIQ payment.</p>"
        f"<p>Amount due: <strong>SAR {float(invoice.total_amount or 0):,.2f}</strong><br>"
        f"Card ending: <strong>{html.escape(last4)}</strong><br>"
        f"Next retry date: <strong>{next_retry_date.strftime('%d %B %Y')}</strong></p>"
        "<p>Please update your payment method if needed before the retry attempt.</p>"
    )
    return _send_billing_email(
        user,
        subject="BanaaIQ - Payment Failed, We Will Retry",
        preheader="Your payment did not go through, but we will retry automatically.",
        title="Payment Retry Scheduled",
        body_html=body_html,
        cta_text="Update Payment Method",
        cta_url=billing_url,
    )


def send_payment_failed_final_email(user):
    billing_url = _absolute_url("billing")
    body_html = (
        "<p>We were unable to process your payment after multiple attempts.</p>"
        "<p>Please update your payment method from the billing dashboard to avoid service interruption and account suspension.</p>"
    )
    return _send_billing_email(
        user,
        subject="BanaaIQ - Action Required: Payment Unsuccessful",
        preheader="Please update your payment method to avoid service interruption.",
        title="Payment Action Required",
        body_html=body_html,
        cta_text="Open Billing",
        cta_url=billing_url,
    )


def send_cancellation_email(user, access_until):
    pricing_url = _absolute_url("pricing")
    access_until_text = access_until.strftime("%d %B %Y")
    body_html = (
        "<p>Your BanaaIQ subscription has been cancelled.</p>"
        f"<p>You will continue to have access until <strong>{html.escape(access_until_text)}</strong>.</p>"
        "<p>Your feedback is appreciated, and your data will remain safely available during the retention period if you decide to return.</p>"
    )
    return _send_billing_email(
        user,
        subject="BanaaIQ Subscription Cancelled",
        preheader="Your subscription has been cancelled, and your access end date is confirmed.",
        title="Subscription Cancelled",
        body_html=body_html,
        cta_text="View Plans",
        cta_url=pricing_url,
    )
