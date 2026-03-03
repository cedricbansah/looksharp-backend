import uuid

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsVerified
from apps.users.models import User

from .models import Withdrawal
from .serializers import (
    AdminWithdrawalUpdateSerializer,
    WithdrawalCreateSerializer,
    WithdrawalListSerializer,
)


def _transfer_reference() -> str:
    return f"wd_{uuid.uuid4().hex}"


class WithdrawalListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/withdrawals/  - create a pending withdrawal (user must be verified)
    GET  /api/v1/withdrawals/  - list the authenticated user's withdrawals
    """

    permission_classes = [IsAuthenticated, IsVerified]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == "POST":
            self.throttle_scope = "withdrawal_create"
            throttles.append(ScopedRateThrottle())
        return throttles

    def get_queryset(self):
        return Withdrawal.objects.filter(
            user_id=self.request.user.id,
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WithdrawalCreateSerializer
        return WithdrawalListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(id=request.user.id)
            requested_points = serializer.validated_data["points_converted"]

            if not user.recipient_code:
                return DRFResponse(
                    {"error": "User has no transfer recipient configured."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if requested_points > user.points:
                return DRFResponse(
                    {"error": "Insufficient points for this withdrawal."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            has_active_withdrawal = Withdrawal.objects.filter(
                user_id=user.id,
                status__in=["pending", "processing"],
            ).exists()
            if has_active_withdrawal:
                return DRFResponse(
                    {"error": "An active withdrawal already exists for this user."},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                withdrawal = serializer.save(
                    user_id=user.id,
                    status="pending",
                    recipient_code=user.recipient_code,
                    transfer_reference=_transfer_reference(),
                )
            except IntegrityError:
                return DRFResponse(
                    {"error": "transfer_reference already exists."},
                    status=status.HTTP_409_CONFLICT,
                )

        return DRFResponse(
            WithdrawalListSerializer(withdrawal).data,
            status=status.HTTP_201_CREATED,
        )


class AdminWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = WithdrawalListSerializer

    def get_queryset(self):
        return Withdrawal.objects.all().order_by("-created_at")


class AdminWithdrawalUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=AdminWithdrawalUpdateSerializer,
        responses={
            200: WithdrawalListSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        description="Update withdrawal status to completed or failed.",
    )
    def patch(self, request, withdrawal_id):
        serializer = AdminWithdrawalUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            withdrawal = Withdrawal.objects.select_for_update().filter(id=withdrawal_id).first()
            if not withdrawal:
                return DRFResponse({"error": "Withdrawal not found."}, status=status.HTTP_404_NOT_FOUND)

            if withdrawal.status in {"completed", "failed"}:
                return DRFResponse(
                    {"error": "Withdrawal is already in a terminal state."},
                    status=status.HTTP_409_CONFLICT,
                )

            user = User.objects.select_for_update().filter(id=withdrawal.user_id).first()
            if not user:
                return DRFResponse({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            target_status = serializer.validated_data["status"]
            if target_status == "completed":
                if withdrawal.points_converted > user.points:
                    return DRFResponse(
                        {"error": "Insufficient points to complete this withdrawal."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                User.objects.filter(id=user.id).update(points=F("points") - withdrawal.points_converted)
                withdrawal.status = "completed"
                withdrawal.completed_at = timezone.now()
                withdrawal.failure_reason = ""
            else:
                withdrawal.status = "failed"
                withdrawal.failure_reason = serializer.validated_data["failure_reason"]
                withdrawal.completed_at = None

            withdrawal.save(update_fields=["status", "failure_reason", "completed_at", "updated_at"])

        return DRFResponse(WithdrawalListSerializer(withdrawal).data, status=status.HTTP_200_OK)
