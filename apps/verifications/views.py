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
        responses={200: VerificationListSerializer, 404: OpenApiTypes.OBJECT},
        description="Approve a verification and mark user as verified.",
    )
    def post(self, request, verification_id):
        with transaction.atomic():
            verification = Verification.objects.select_for_update().filter(id=verification_id).first()
            if not verification:
                return Response({"error": "Verification not found."}, status=status.HTTP_404_NOT_FOUND)

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

            User.objects.filter(id=verification.user_id).update(is_verified=True)

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
            201: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
        description="Create a Paystack transfer recipient from verification data.",
    )
    def post(self, request, verification_id):
        verification = Verification.objects.filter(id=verification_id).first()
        if not verification:
            return Response({"error": "Verification not found."}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({"error": "Paystack request failed"}, status=status.HTTP_502_BAD_GATEWAY)

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

        User.objects.filter(id=verification.user_id).update(recipient_code=recipient_code)
        logger.info(
            "Recipient created for verification=%s user=%s",
            verification_id,
            verification.user_id,
        )
        return Response({"recipient_code": recipient_code}, status=status.HTTP_201_CREATED)
