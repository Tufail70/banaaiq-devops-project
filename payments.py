"""
payments.py — Provider-agnostic payment abstraction.

Switch payment gateway via the PAYMENT_PROVIDER environment variable:
  mock      — dev/test, always succeeds (default)
  razorpay  — India live payments via Razorpay
  stripe    — KSA/Gulf (future)

All route code calls get_payment_provider() — no gateway-specific
imports outside this file.
"""

import random
import string
from abc import ABC, abstractmethod
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class PaymentProvider(ABC):
    @abstractmethod
    def create_subscription(self, user, plan, currency): ...

    @abstractmethod
    def cancel_subscription(self, subscription_id): ...

    @abstractmethod
    def verify_webhook(self, payload, signature): ...

    @abstractmethod
    def get_customer_payment_methods(self, customer_id): ...

    @abstractmethod
    def create_invoice_tax_context(self, invoice): ...

    @abstractmethod
    def get_publishable_key(self): ...


# ---------------------------------------------------------------------------
# Mock provider (dev / CI)
# ---------------------------------------------------------------------------

def _random_id(prefix, length=10):
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase, k=length))}"


class MockPaymentProvider(PaymentProvider):
    """Dev/testing — fake successful payments, no external calls."""

    def create_subscription(self, user, plan, currency="INR"):
        amount = float(plan.get_price(currency) or 0)
        return {
            "subscription_id": f"mock_{user.id}_{plan.id}",
            "status": "active",
            "currency": currency,
            "amount": amount,
            "next_billing_date": datetime.utcnow() + timedelta(days=30),
        }

    def cancel_subscription(self, subscription_id):
        return {"status": "cancelled", "id": subscription_id}

    def verify_webhook(self, payload, signature):
        return True

    def get_customer_payment_methods(self, customer_id):
        return [{"type": "card", "last4": "4242", "brand": "Visa"}]

    def create_invoice_tax_context(self, invoice):
        return {
            "tax_label": "Tax",
            "tax_rate": 0,
            "jurisdiction": "Test",
        }

    def get_publishable_key(self):
        return "pk_mock_not_configured_yet"

    # ── Legacy flat-function compatibility ──────────────────────────────────
    def charge_invoice(self, invoice, payment_method_token):
        return {"status": "succeeded", "id": f"pi_mock_{invoice.id}"}

    def create_customer(self, user):
        return _random_id("cus_mock")

    def update_payment_method(self, customer_id, card_token):
        return {
            "id": f"pm_mock_{card_token}",
            "customer": customer_id,
            "card": {"last4": "4242", "brand": "Visa", "exp_month": 12, "exp_year": 2027},
        }


# ---------------------------------------------------------------------------
# Razorpay provider (India)
# ---------------------------------------------------------------------------

class RazorpayProvider(PaymentProvider):

    def __init__(self):
        import razorpay
        from flask import current_app
        self.client = razorpay.Client(
            auth=(
                current_app.config["RAZORPAY_KEY_ID"],
                current_app.config["RAZORPAY_KEY_SECRET"],
            )
        )

    def create_subscription(self, user, plan, currency="INR"):
        from flask import current_app
        razorpay_plan_id = self._ensure_plan(plan, currency)
        total_count = 12 if plan.billing_cycle == "monthly" else 1
        sub = self.client.subscription.create({
            "plan_id": razorpay_plan_id,
            "customer_notify": 1,
            "total_count": total_count,
            "quantity": 1,
            "notes": {
                "user_id": str(user.id),
                "plan_code": plan.name,
                "platform": "BanaaIQ",
            },
        })
        return {
            "subscription_id": sub["id"],
            "status": sub["status"],
            "short_url": sub.get("short_url"),
            "currency": currency,
            "amount": float(plan.get_price(currency) or 0),
        }

    def cancel_subscription(self, subscription_id):
        return self.client.subscription.cancel(
            subscription_id, {"cancel_at_cycle_end": 1}
        )

    def verify_webhook(self, payload, signature):
        from flask import current_app
        try:
            import razorpay.utility as util
            util.Utility.verify_webhook_signature(
                payload,
                signature,
                current_app.config["RAZORPAY_WEBHOOK_SECRET"],
            )
            return True
        except Exception:
            return False

    def get_customer_payment_methods(self, customer_id):
        # Razorpay doesn't expose saved cards via API in same way as Stripe;
        # return empty — payment method is captured per-transaction.
        return []

    def create_invoice_tax_context(self, invoice):
        from flask import current_app
        return {
            "provider": "razorpay",
            "gstin": current_app.config.get("COMPANY_GSTIN") or "GSTIN-PENDING",
            "company_legal_name": current_app.config.get("COMPANY_LEGAL_NAME", "BanaaIQ Technologies"),
            "company_address_line_1": current_app.config.get("COMPANY_ADDRESS_LINE_1", ""),
            "company_address_line_2": current_app.config.get("COMPANY_ADDRESS_LINE_2", ""),
            "company_city": current_app.config.get("COMPANY_CITY", ""),
            "company_state": current_app.config.get("COMPANY_STATE", ""),
            "company_pin": current_app.config.get("COMPANY_PIN", ""),
            "company_state_code": current_app.config.get("COMPANY_STATE_CODE", ""),
            # Use IGST 18% by default (interstate) — safe for MVP before CA review
            "tax_label": "IGST 18%",
            "tax_rate": 18,
            "hsn_sac": "998313",  # IT software services
            "jurisdiction": "India",
            "reverse_charge": "No",
        }

    def get_publishable_key(self):
        from flask import current_app
        return current_app.config.get("RAZORPAY_KEY_ID", "")

    def _ensure_plan(self, plan, currency):
        """Get or create Razorpay plan_id for (plan, currency, billing_cycle), cached in DB."""
        from flask import current_app
        from models import GatewayPlan, db

        cache_key = f"{plan.name}_{currency}_{plan.billing_cycle}"
        existing = GatewayPlan.query.filter_by(
            provider="razorpay",
            cache_key=cache_key,
        ).first()
        if existing:
            return existing.gateway_plan_id

        amount_paise = int(float(plan.get_price(currency) or 0) * 100)
        period = "monthly" if plan.billing_cycle == "monthly" else "yearly"
        rzp_plan = self.client.plan.create({
            "period": period,
            "interval": 1,
            "item": {
                "name": f"BanaaIQ {plan.display_name} ({currency})",
                "amount": amount_paise,
                "currency": currency,
                "description": f"BanaaIQ {plan.display_name} subscription",
            },
        })
        cached = GatewayPlan(
            provider="razorpay",
            cache_key=cache_key,
            gateway_plan_id=rzp_plan["id"],
            plan_code=plan.name,
            currency=currency,
            amount=float(plan.get_price(currency) or 0),
        )
        db.session.add(cached)
        db.session.commit()
        return rzp_plan["id"]

    # ── Legacy compatibility ─────────────────────────────────────────────────
    def charge_invoice(self, invoice, payment_method_token):
        # Razorpay subscriptions auto-charge; this path is for one-off charges.
        # Return mock success — real charge happens via subscription webhook.
        return {"status": "succeeded", "id": f"rzp_{invoice.id}"}

    def create_customer(self, user):
        customer = self.client.customer.create({
            "name": user.full_name or user.email,
            "email": user.email,
            "contact": user.phone or "",
        })
        return customer.get("id", _random_id("cus_rzp"))

    def update_payment_method(self, customer_id, card_token):
        return {"id": card_token, "customer": customer_id}


# ---------------------------------------------------------------------------
# Stripe provider (future — KSA/Gulf)
# ---------------------------------------------------------------------------

class StripeProvider(PaymentProvider):
    """Placeholder — implement when KSA launch is ready."""

    def __init__(self):
        from flask import current_app
        try:
            import stripe
            stripe.api_key = current_app.config["STRIPE_API_KEY"]
            self._stripe = stripe
        except ImportError:
            raise RuntimeError(
                "stripe package not installed. Add stripe>=7.0.0 to requirements.txt"
            )

    def create_subscription(self, user, plan, currency="SAR"):
        raise NotImplementedError("Stripe provider not yet implemented. Set PAYMENT_PROVIDER=mock.")

    def cancel_subscription(self, subscription_id):
        raise NotImplementedError("Stripe provider not yet implemented.")

    def verify_webhook(self, payload, signature):
        raise NotImplementedError("Stripe provider not yet implemented.")

    def get_customer_payment_methods(self, customer_id):
        raise NotImplementedError("Stripe provider not yet implemented.")

    def create_invoice_tax_context(self, invoice):
        return {
            "tax_label": "VAT 15% (ZATCA)",
            "tax_rate": 15,
            "jurisdiction": "Saudi Arabia",
        }

    def get_publishable_key(self):
        from flask import current_app
        return current_app.config.get("STRIPE_PUBLISHABLE_KEY", "")

    def charge_invoice(self, invoice, payment_method_token):
        raise NotImplementedError("Stripe provider not yet implemented.")

    def create_customer(self, user):
        raise NotImplementedError("Stripe provider not yet implemented.")

    def update_payment_method(self, customer_id, card_token):
        raise NotImplementedError("Stripe provider not yet implemented.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_payment_provider() -> PaymentProvider:
    """Return the active PaymentProvider based on PAYMENT_PROVIDER config."""
    from flask import current_app
    provider_name = current_app.config.get("PAYMENT_PROVIDER", "mock").lower()
    if provider_name == "razorpay":
        return RazorpayProvider()
    if provider_name == "stripe":
        return StripeProvider()
    return MockPaymentProvider()


# ---------------------------------------------------------------------------
# Legacy flat-function wrappers (backward compat — called from app.py)
# Route code can call these OR call get_payment_provider() directly.
# ---------------------------------------------------------------------------

def create_customer(user):
    return get_payment_provider().create_customer(user)


def create_subscription(customer_id, plan_name, billing_cycle):
    """Legacy signature — returns mock-compatible dict."""
    return {
        "id": _random_id("sub_mock"),
        "status": "active",
        "customer": customer_id,
        "plan_name": plan_name,
        "billing_cycle": billing_cycle,
        "created_at": datetime.utcnow().isoformat(),
    }


def cancel_subscription(gateway_subscription_id):
    return get_payment_provider().cancel_subscription(gateway_subscription_id)


def charge_invoice(invoice, payment_method_token):
    return get_payment_provider().charge_invoice(invoice, payment_method_token)


def update_payment_method(customer_id, card_token):
    return get_payment_provider().update_payment_method(customer_id, card_token)


def get_publishable_key():
    return get_payment_provider().get_publishable_key()
