import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    """HMAC SHA512 verification - identical to the Cloud Function."""
    if not signature or not settings.PAYSTACK_SECRET_KEY:
        return False
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _extract_transfer_details(data: dict):
    """Extract transfer_code + reference from 3 Paystack payload formats."""
    if "reference" in data and "transfer_code" not in data:
        return None, data.get("reference")
    if "transfer_code" in data:
        return data.get("transfer_code"), data.get("reference")
    if data.get("event") == "transferrequest.approval-required":
        transfers = data.get("data", {}).get("transfers", [])
        if transfers:
            return transfers[0].get("transfer_code"), transfers[0].get("reference")
        return None, None
    if "data" in data and "transfer_code" in data.get("data", {}):
        return data["data"]["transfer_code"], data["data"].get("reference")
    return None, None


class PaystackWebhookView(APIView):
    """
    POST /api/v1/webhooks/paystack/
    Handles Paystack transfer approval/decline events.
    No auth - HMAC signature is the authentication mechanism.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Read raw bytes BEFORE any parsing (required for HMAC)
        raw_body = request.body
        if not raw_body:
            return Response({"error": "Empty body"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Verify Paystack signature
        signature = request.headers.get("X-Paystack-Signature", "")
        if not _verify_signature(raw_body, signature):
            logger.warning("Paystack webhook: invalid signature")
            return Response(
                {"error": "Invalid signature"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 3. Parse JSON
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Extract transfer identifiers
        transfer_code, reference = _extract_transfer_details(data)
        if not transfer_code and not reference:
            logger.warning("Paystack webhook: no identifiers in event %s", data.get("event"))
            return Response(
                {"error": "Missing transfer identifiers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Validate and transition withdrawal state
        identifier = reference or transfer_code
        identifier_type = "transfer_reference" if reference else "transfer_code"

        result = _validate_and_transition(identifier, identifier_type, transfer_code)

        if result["success"]:
            return Response({}, status=status.HTTP_200_OK)
        return Response({"error": result["reason"]}, status=status.HTTP_400_BAD_REQUEST)


def _validate_and_transition(identifier, identifier_type, transfer_code):
    """
    Validate withdrawal and transition its status.
    Mirrors validate_transfer_request() + update_withdrawal_status() from the Cloud Function.
    """
    from apps.users.models import User
    from apps.withdrawals.models import Withdrawal

    try:
        with transaction.atomic():
            withdrawal = (
                Withdrawal.objects.select_for_update()
                .filter(**{identifier_type: identifier})
                .first()
            )
            if not withdrawal:
                logger.error("Withdrawal not found: %s=%s", identifier_type, identifier)
                return {"success": False, "reason": "Transfer not found"}

            if withdrawal.status == "completed":
                logger.info("Webhook replay ignored for completed withdrawal %s", withdrawal.id)
                return {"success": True}

            if withdrawal.status == "failed":
                logger.info("Webhook replay ignored for failed withdrawal %s", withdrawal.id)
                return {"success": True}

            if withdrawal.status == "processing":
                if (
                    transfer_code
                    and withdrawal.transfer_code
                    and withdrawal.transfer_code != transfer_code
                ):
                    return {
                        "success": False,
                        "reason": "Transfer code mismatch for processing withdrawal",
                    }
                if transfer_code and not withdrawal.transfer_code:
                    withdrawal.transfer_code = transfer_code
                    withdrawal.updated_at = timezone.now()
                    withdrawal.save(update_fields=["transfer_code", "updated_at"])
                logger.info(
                    "Webhook replay ignored for processing withdrawal %s", withdrawal.id
                )
                return {"success": True}

            if withdrawal.status != "pending":
                return {"success": False, "reason": f"Invalid withdrawal status: {withdrawal.status}"}

            user = User.objects.select_for_update().filter(id=withdrawal.user_id).first()
            if not user:
                _mark_failed(withdrawal, transfer_code, "User not found")
                return {"success": False, "reason": "User not found"}

            if not user.is_verified:
                _mark_failed(withdrawal, transfer_code, "User not verified")
                return {"success": False, "reason": "User not verified"}

            if withdrawal.points_converted > user.points:
                _mark_failed(withdrawal, transfer_code, "Insufficient points")
                return {"success": False, "reason": "Insufficient points"}

            pending_count = Withdrawal.objects.filter(
                user_id=withdrawal.user_id,
                status__in=["pending", "processing"],
            ).count()
            if pending_count > 1:
                _mark_failed(withdrawal, transfer_code, "Multiple pending withdrawals")
                return {"success": False, "reason": "Multiple pending withdrawals"}

            # All checks passed - approve
            withdrawal.status = "processing"
            if transfer_code:
                withdrawal.transfer_code = transfer_code
            withdrawal.updated_at = timezone.now()
            withdrawal.save(update_fields=["status", "transfer_code", "updated_at"])

            logger.info("Withdrawal %s approved -> processing", withdrawal.id)
            return {"success": True}

    except Exception as exc:
        logger.exception("Error in webhook validation: %s", exc)
        return {"success": False, "reason": "Internal error"}


def _mark_failed(withdrawal, transfer_code, reason):
    withdrawal.status = "failed"
    withdrawal.failure_reason = reason
    if transfer_code:
        withdrawal.transfer_code = transfer_code
    withdrawal.updated_at = timezone.now()
    withdrawal.save(update_fields=["status", "failure_reason", "transfer_code", "updated_at"])
    logger.warning("Withdrawal %s -> failed: %s", withdrawal.id, reason)
