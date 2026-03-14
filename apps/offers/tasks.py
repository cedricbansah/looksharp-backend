import logging

from celery import shared_task
from django.utils import timezone

from .models import Offer

logger = logging.getLogger(__name__)


@shared_task(queue="bulk")
def notify_users_new_offer(offer_id: str) -> dict:
    """Broadcast an SMS to all users with phone numbers when an offer goes active."""
    from apps.users.models import User
    from services.hubtel import normalize_phone_number, send_bulk_sms

    try:
        offer = Offer.objects.get(id=offer_id)
    except Offer.DoesNotExist:
        logger.warning("notify_users_new_offer: offer %s not found, skipping", offer_id)
        return {"success": False, "detail": "offer not found"}

    message = (
        f"New offer available: {offer.title}. "
        "Open the LookSharp app to participate."
    )
    users = User.objects.exclude(phone="").only("phone")
    recipients = []
    failed = 0
    for user in users.iterator():
        try:
            recipients.append(normalize_phone_number(user.phone))
        except Exception:
            logger.exception(
                "notify_users_new_offer: invalid phone number for offer=%s", offer_id
            )
            failed += 1

    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        logger.info("notify_users_new_offer: offer=%s sent=0 failed=%d", offer_id, failed)
        return {"success": True, "offer_id": offer_id, "sent": 0, "failed": failed}

    try:
        send_bulk_sms(recipients, message)
        sent = len(recipients)
    except Exception:
        logger.exception("notify_users_new_offer: failed bulk SMS send (offer=%s)", offer_id)
        failed += len(recipients)
        sent = 0

    logger.info(
        "notify_users_new_offer: offer=%s sent=%d failed=%d", offer_id, sent, failed
    )
    return {"success": True, "offer_id": offer_id, "sent": sent, "failed": failed}


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
