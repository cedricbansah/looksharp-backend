import logging

from celery import shared_task
from django.utils import timezone

from .models import Offer

logger = logging.getLogger(__name__)


def _days_remaining(end_date):
    if not end_date:
        return 0
    now = timezone.now()
    delta = end_date - now
    return max(0, delta.days)


@shared_task(queue="default")
def recompute_status() -> dict:
    now = timezone.now()
    error_count = 0

    ended_count = Offer.objects.filter(
        status="active",
        end_date__isnull=False,
        end_date__lte=now,
    ).update(status="inactive", days_remaining=0, updated_at=now)

    updated_offers = []
    active_offers = Offer.objects.filter(
        status="active",
        end_date__isnull=False,
        end_date__gt=now,
    ).only("id", "end_date", "days_remaining")
    for offer in active_offers.iterator():
        try:
            days_remaining = _days_remaining(offer.end_date)
            if offer.days_remaining == days_remaining:
                continue
            offer.days_remaining = days_remaining
            offer.updated_at = now
            updated_offers.append(offer)
        except Exception:
            logger.exception("Failed to recompute offer status for %s", offer.id)
            error_count += 1

    if updated_offers:
        Offer.objects.bulk_update(updated_offers, fields=["days_remaining", "updated_at"])
    updated_count = len(updated_offers)

    return {
        "success": True,
        "updated_count": updated_count,
        "ended_count": ended_count,
        "error_count": error_count,
        "total_processed": updated_count + ended_count + error_count,
    }
