import logging

from celery import shared_task
from django.utils import timezone

from .models import Verification

logger = logging.getLogger(__name__)


@shared_task(queue="default")
def notify_user_kyc_decision(verification_id: str) -> dict:
    """Send an SMS to a user informing them of their KYC approval or rejection."""
    from apps.users.models import User
    from services.hubtel import send_sms

    try:
        verification = Verification.objects.select_related().get(id=verification_id)
    except Verification.DoesNotExist:
        logger.warning("notify_user_kyc_decision: verification %s not found, skipping", verification_id)
        return {"success": False, "detail": "verification not found"}

    if verification.notification_sent:
        logger.info(
            "notify_user_kyc_decision: notification already sent for verification=%s, skipping",
            verification_id,
        )
        return {"success": True, "detail": "already sent"}

    try:
        user = User.objects.get(id=verification.user_id)
    except User.DoesNotExist:
        logger.warning(
            "notify_user_kyc_decision: user %s not found for verification=%s",
            verification.user_id,
            verification_id,
        )
        return {"success": False, "detail": "user not found"}

    if not user.phone:
        logger.info(
            "notify_user_kyc_decision: user %s has no phone, skipping", user.id
        )
        return {"success": False, "detail": "user has no phone"}

    first_name = user.first_name or "there"

    if verification.status == "approved":
        message = (
            f"Hi {first_name}, your LookSharp identity verification has been approved. "
            "You can now access all features."
        )
    elif verification.status == "rejected":
        reason = verification.rejection_reason or "please check the app for details"
        message = (
            f"Hi {first_name}, your LookSharp identity verification was not approved. "
            f"Reason: {reason}. Please resubmit."
        )
    else:
        logger.info(
            "notify_user_kyc_decision: verification=%s has status=%s, skipping SMS",
            verification_id,
            verification.status,
        )
        return {"success": False, "detail": f"no SMS for status {verification.status}"}

    try:
        send_sms(user.phone, message)
    except Exception:
        logger.exception(
            "notify_user_kyc_decision: failed to send SMS for verification=%s", verification_id
        )
        raise

    Verification.objects.filter(id=verification_id).update(
        notification_sent=True,
        notification_sent_at=timezone.now(),
    )
    logger.info("notify_user_kyc_decision: SMS sent for verification=%s", verification_id)
    return {"success": True, "verification_id": verification_id}
