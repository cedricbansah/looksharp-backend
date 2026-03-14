import logging

from celery import shared_task
from django.utils import timezone

from .models import Survey

logger = logging.getLogger(__name__)


@shared_task(queue="bulk")
def notify_users_new_survey(survey_id: str) -> dict:
    """Broadcast an SMS to all users with phone numbers when a survey goes active."""
    from apps.users.models import User
    from services.hubtel import normalize_phone_number, send_bulk_sms

    try:
        survey = Survey.objects.get(id=survey_id)
    except Survey.DoesNotExist:
        logger.warning("notify_users_new_survey: survey %s not found, skipping", survey_id)
        return {"success": False, "detail": "survey not found"}

    message = (
        f"New survey available: {survey.title}. "
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
                "notify_users_new_survey: invalid phone number for survey=%s", survey_id
            )
            failed += 1

    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        logger.info("notify_users_new_survey: survey=%s sent=0 failed=%d", survey_id, failed)
        return {"success": True, "survey_id": survey_id, "sent": 0, "failed": failed}

    try:
        send_bulk_sms(recipients, message)
        sent = len(recipients)
    except Exception:
        logger.exception("notify_users_new_survey: failed bulk SMS send (survey=%s)", survey_id)
        failed += len(recipients)
        sent = 0

    logger.info(
        "notify_users_new_survey: survey=%s sent=%d failed=%d", survey_id, sent, failed
    )
    return {"success": True, "survey_id": survey_id, "sent": sent, "failed": failed}


@shared_task(queue="default")
def recompute_status() -> dict:
    now = timezone.now()
    completed_count = Survey.objects.filter(
        status="active",
        end_date__isnull=False,
        end_date__lte=now,
    ).update(status="completed", updated_at=now)

    if completed_count:
        from apps.counters.tasks import recompute_active_surveys

        recompute_active_surveys.delay()

    return {
        "success": True,
        "completed_count": completed_count,
    }
