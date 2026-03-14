import logging

import requests as http_requests
from celery import shared_task
from django.db import transaction
from django.utils import timezone

import services.paystack as paystack_service

logger = logging.getLogger(__name__)


def _extract_paystack_error_message(exc: Exception) -> str:
    if not isinstance(exc, http_requests.HTTPError) or exc.response is None:
        return str(exc) or "Paystack request failed"

    try:
        payload = exc.response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("message", "gateway_response", "status_description"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        for key in ("message", "error", "statusDescription"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    if exc.response.text.strip():
        return exc.response.text.strip()
    return f"Paystack request failed (HTTP {exc.response.status_code})"


def _mark_failed_locked(withdrawal, reason: str) -> None:
    withdrawal.status = "failed"
    withdrawal.failure_reason = reason
    withdrawal.completed_at = None
    withdrawal.updated_at = timezone.now()
    withdrawal.save(update_fields=["status", "failure_reason", "completed_at", "updated_at"])


@shared_task(bind=True, queue="default", max_retries=3)
def initiate_withdrawal_transfer(self, withdrawal_id: str) -> dict:
    from apps.users.models import User

    from .models import Withdrawal

    with transaction.atomic():
        withdrawal = Withdrawal.objects.select_for_update().filter(id=withdrawal_id).first()
        if not withdrawal:
            logger.warning("initiate_withdrawal_transfer: withdrawal %s not found", withdrawal_id)
            return {"success": False, "detail": "withdrawal not found"}

        if withdrawal.status != "pending":
            logger.info(
                "initiate_withdrawal_transfer: withdrawal %s already %s, skipping",
                withdrawal_id,
                withdrawal.status,
            )
            return {"success": True, "detail": "already processed", "status": withdrawal.status}

        user = User.objects.select_for_update().filter(id=withdrawal.user_id).first()
        if not user:
            _mark_failed_locked(withdrawal, "User not found")
            return {"success": False, "detail": "user not found"}

        if not withdrawal.recipient_code:
            _mark_failed_locked(withdrawal, "User has no transfer recipient configured.")
            return {"success": False, "detail": "recipient code missing"}

        if withdrawal.points_converted > user.points:
            _mark_failed_locked(withdrawal, "Insufficient points for this withdrawal.")
            return {"success": False, "detail": "insufficient points"}

        amount_kobo = int(withdrawal.amount_ghs * 100)
        recipient_code = withdrawal.recipient_code
        transfer_reference = withdrawal.transfer_reference

    try:
        transfer_data = paystack_service.initiate_transfer(
            recipient=recipient_code,
            amount_kobo=amount_kobo,
            reference=transfer_reference,
        )
    except http_requests.HTTPError as exc:
        detail = _extract_paystack_error_message(exc)
        logger.error("initiate_withdrawal_transfer: terminal paystack error for %s: %s", withdrawal_id, detail)
        with transaction.atomic():
            withdrawal = Withdrawal.objects.select_for_update().filter(id=withdrawal_id).first()
            if not withdrawal or withdrawal.status != "pending":
                return {"success": False, "detail": detail}
            _mark_failed_locked(withdrawal, detail)
        return {"success": False, "detail": detail}
    except http_requests.RequestException as exc:
        countdown = 2 ** self.request.retries
        logger.warning(
            "initiate_withdrawal_transfer: retrying withdrawal %s after paystack transport error: %s",
            withdrawal_id,
            exc,
        )
        raise self.retry(exc=exc, countdown=countdown)

    transfer_code = (
        transfer_data.get("data", {}).get("transfer_code")
        or transfer_data.get("transfer_code")
        or ""
    )

    with transaction.atomic():
        withdrawal = Withdrawal.objects.select_for_update().filter(id=withdrawal_id).first()
        if not withdrawal:
            logger.warning(
                "initiate_withdrawal_transfer: withdrawal %s disappeared after paystack success",
                withdrawal_id,
            )
            return {"success": False, "detail": "withdrawal not found"}

        if withdrawal.status != "pending":
            logger.info(
                "initiate_withdrawal_transfer: withdrawal %s became %s before update, skipping",
                withdrawal_id,
                withdrawal.status,
            )
            return {"success": True, "detail": "already processed", "status": withdrawal.status}

        if not transfer_code:
            _mark_failed_locked(withdrawal, "Paystack response missing transfer_code.")
            return {"success": False, "detail": "transfer code missing"}

        withdrawal.status = "processing"
        withdrawal.transfer_code = transfer_code
        withdrawal.failure_reason = ""
        withdrawal.updated_at = timezone.now()
        withdrawal.save(update_fields=["status", "transfer_code", "failure_reason", "updated_at"])

    logger.info(
        "initiate_withdrawal_transfer: withdrawal %s moved to processing",
        withdrawal_id,
    )
    return {"success": True, "withdrawal_id": withdrawal_id, "status": "processing"}
