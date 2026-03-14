import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
import requests as http_requests
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

import services.paystack as paystack_service
from apps.core.permissions import IsAdmin
from apps.users.models import User

from .models import Verification
from .serializers import (
    VerificationCreateSerializer,
    VerificationListSerializer,
    VerificationRejectSerializer,
)

logger = logging.getLogger(__name__)


def _verification_actionable_for_recipient(verification: Verification) -> bool:
    return verification.status in {"pending", "approved"}


def _paystack_error_message(exc: http_requests.HTTPError) -> str:
    response = exc.response
    if response is None:
        return "Paystack request failed."

    try:
        payload = response.json()
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

    if response.text.strip():
        return response.text.strip()
    return "Paystack request failed."


class VerificationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == "POST":
            self.throttle_scope = "verification_create"
            throttles.append(ScopedRateThrottle())
        return throttles

    def get_queryset(self):
        return Verification.objects.filter(user_id=self.request.user.id).order_by("-submitted_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VerificationCreateSerializer
        return VerificationListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = serializer.save(user_id=request.user.id)
        return Response(
            VerificationListSerializer(verification).data,
            status=status.HTTP_201_CREATED,
        )


class AdminVerificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = VerificationListSerializer

    def get_queryset(self):
        return Verification.objects.all().order_by("-submitted_at")


class AdminVerificationApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=None,
        responses={200: VerificationListSerializer, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT},
        description="Approve a verification and mark user as verified.",
    )
    def post(self, request, verification_id):
        with transaction.atomic():
            verification = Verification.objects.select_for_update().filter(id=verification_id).first()
            if not verification:
                return Response({"error": "Verification not found."}, status=status.HTTP_404_NOT_FOUND)

            if verification.status == "approved":
                return Response({"error": "Verification is already approved."}, status=status.HTTP_409_CONFLICT)
            if verification.status == "rejected":
                return Response({"error": "Verification is already rejected."}, status=status.HTTP_409_CONFLICT)

            user = User.objects.select_for_update().filter(id=verification.user_id).first()
            if not user:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            if not user.recipient_code:
                return Response(
                    {"error": "Generate recipient code before approving this verification."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verification.status = "approved"
            verification.rejection_reason = ""
            verification.reviewed_by = request.user.id
            verification.reviewed_at = timezone.now()
            verification.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                ]
            )

            user.is_verified = True
            user.save(update_fields=["is_verified"])

        from .tasks import notify_user_kyc_decision
        notify_user_kyc_decision.delay(verification.id)
        logger.info("Verification approved: verification=%s admin=%s", verification_id, request.user.id)
        return Response(VerificationListSerializer(verification).data)


class AdminVerificationRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=VerificationRejectSerializer,
        responses={200: VerificationListSerializer, 404: OpenApiTypes.OBJECT},
        description="Reject a verification with a reason and unverify the user.",
    )
    def post(self, request, verification_id):
        payload = VerificationRejectSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        with transaction.atomic():
            verification = Verification.objects.select_for_update().filter(id=verification_id).first()
            if not verification:
                return Response({"error": "Verification not found."}, status=status.HTTP_404_NOT_FOUND)

            verification.status = "rejected"
            verification.rejection_reason = payload.validated_data["rejection_reason"]
            verification.reviewed_by = request.user.id
            verification.reviewed_at = timezone.now()
            verification.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "reviewed_by",
                    "reviewed_at",
                    "updated_at",
                ]
            )

            User.objects.filter(id=verification.user_id).update(is_verified=False)

        from .tasks import notify_user_kyc_decision
        notify_user_kyc_decision.delay(verification.id)
        logger.info("Verification rejected: verification=%s admin=%s", verification_id, request.user.id)
        return Response(VerificationListSerializer(verification).data)


class AdminCreateRecipientView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=None,
        responses={
            200: OpenApiTypes.OBJECT,
            201: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
        description="Create a Paystack transfer recipient from verification data.",
    )
    def post(self, request, verification_id):
        with transaction.atomic():
            verification = Verification.objects.select_for_update().filter(id=verification_id).first()
            if not verification:
                return Response({"error": "Verification not found."}, status=status.HTTP_404_NOT_FOUND)

            if not _verification_actionable_for_recipient(verification):
                return Response(
                    {"error": f"Verification is not actionable in status {verification.status}."},
                    status=status.HTTP_409_CONFLICT,
                )

            user = User.objects.select_for_update().filter(id=verification.user_id).first()
            if not user:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            if user.recipient_code:
                return Response({"recipient_code": user.recipient_code}, status=status.HTTP_200_OK)

        try:
            recipient_data = paystack_service.create_transfer_recipient(
                name=verification.full_name,
                account_number=verification.mobile_number,
                bank_code=verification.network_provider,
                type="mobile_money",
                currency="GHS",
            )
        except http_requests.HTTPError as exc:
            logger.error("Paystack create_recipient failed: %s", exc)
            return Response({"error": _paystack_error_message(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        recipient_code = (
            recipient_data.get("data", {}).get("recipient_code")
            or recipient_data.get("recipient_code")
            or ""
        )
        if not recipient_code:
            return Response(
                {"error": "Paystack response missing recipient_code."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        with transaction.atomic():
            user = User.objects.select_for_update().filter(id=verification.user_id).first()
            if not user:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            if user.recipient_code:
                return Response({"recipient_code": user.recipient_code}, status=status.HTTP_200_OK)

            user.recipient_code = recipient_code
            user.save(update_fields=["recipient_code"])
        logger.info(
            "Recipient created for verification=%s user=%s",
            verification_id,
            verification.user_id,
        )
        return Response({"recipient_code": recipient_code}, status=status.HTTP_201_CREATED)
