import logging

from celery import shared_task
from django.db import transaction
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
    updated_count = 0
    ended_count = 0
    error_count = 0

    active_offers = Offer.objects.filter(status="active", is_deleted=False)
    for offer in active_offers.iterator():
        try:
            if not offer.end_date:
                continue

            days_remaining = _days_remaining(offer.end_date)
            with transaction.atomic():
                locked = Offer.objects.select_for_update().get(id=offer.id)
                locked.days_remaining = days_remaining
                if days_remaining <= 0:
                    locked.status = "inactive"
                    ended_count += 1
                else:
                    updated_count += 1
                locked.save(update_fields=["days_remaining", "status", "updated_at"])
        except Exception:
            logger.exception("Failed to recompute offer status for %s", offer.id)
            error_count += 1

    return {
        "success": True,
        "updated_count": updated_count,
        "ended_count": ended_count,
        "error_count": error_count,
        "total_processed": updated_count + ended_count + error_count,
    }
