from decimal import Decimal

from celery import shared_task
from django.db.models import Sum

from apps.offers.models import Offer
from apps.responses.models import Response
from apps.surveys.models import Survey
from apps.users.models import User
from apps.verifications.models import Verification
from apps.withdrawals.models import Withdrawal

from .models import DashboardCounter


DASHBOARD_COUNTER_ID = "dashboard"


def _counter() -> DashboardCounter:
    obj, _ = DashboardCounter.objects.get_or_create(id=DASHBOARD_COUNTER_ID)
    return obj


@shared_task(queue="default")
def recompute_active_surveys() -> int:
    value = Survey.objects.filter(status="active", is_deleted=False).count()
    counter = _counter()
    counter.active_surveys = value
    counter.save(update_fields=["active_surveys", "updated_at"])
    return value


@shared_task(queue="default")
def recompute_active_offers() -> int:
    value = Offer.objects.filter(status="active", is_deleted=False).count()
    counter = _counter()
    counter.active_offers = value
    counter.save(update_fields=["active_offers", "updated_at"])
    return value


@shared_task(queue="default")
def recompute_total_responses() -> int:
    value = Response.objects.filter(is_deleted=False).count()
    counter = _counter()
    counter.total_responses = value
    counter.save(update_fields=["total_responses", "updated_at"])
    return value


@shared_task(queue="default")
def recompute_total_paid_out() -> str:
    total = (
        Withdrawal.objects.filter(status="completed").aggregate(total=Sum("amount_ghs"))["total"]
        or Decimal("0")
    )
    counter = _counter()
    counter.total_paid_out = total
    counter.save(update_fields=["total_paid_out", "updated_at"])
    return str(total)


@shared_task(queue="default")
def recompute_extended_dashboard() -> dict:
    counter = _counter()
    counter.total_users = User.objects.filter(is_deleted=False).count()
    counter.verified_users = User.objects.filter(is_deleted=False, is_verified=True).count()
    counter.total_points_issued = User.objects.filter(is_deleted=False).aggregate(
        total=Sum("points")
    )["total"] or 0
    counter.pending_verifications = Verification.objects.filter(status="pending").count()
    counter.pending_withdrawals = Withdrawal.objects.filter(
        status__in=["pending", "processing"]
    ).count()
    counter.save(
        update_fields=[
            "total_users",
            "verified_users",
            "total_points_issued",
            "pending_verifications",
            "pending_withdrawals",
            "updated_at",
        ]
    )
    return {
        "total_users": counter.total_users,
        "verified_users": counter.verified_users,
        "total_points_issued": counter.total_points_issued,
        "pending_verifications": counter.pending_verifications,
        "pending_withdrawals": counter.pending_withdrawals,
    }
