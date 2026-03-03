import logging

from django.db import transaction
from django.db.models import F
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin

from .models import User
from .serializers import (
    AdminUserSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)
WELCOME_BONUS_POINTS = 100


def _sync_firebase_admin_claim(user_id: str) -> None:
    from firebase_admin import auth as firebase_auth

    from apps.core.authentication import _get_firebase_app

    _get_firebase_app()
    user_record = firebase_auth.get_user(user_id)
    claims = dict(user_record.custom_claims or {})
    claims["admin"] = True
    firebase_auth.set_custom_user_claims(user_id, claims)


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/users/me/  - return authenticated user's profile
    PATCH /api/v1/users/me/ - update client-writable fields only
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        return UserSerializer


class WelcomeBonusClaimView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Claim one-time welcome bonus for the authenticated user.",
    )
    def post(self, request):
        bonus_awarded = False
        with transaction.atomic():
            user = User.objects.select_for_update().get(id=request.user.id)
            if not user.welcome_bonus_claimed:
                User.objects.filter(id=user.id).update(
                    points=F("points") + WELCOME_BONUS_POINTS,
                    welcome_bonus_claimed=True,
                )
                bonus_awarded = True

        return Response({"success": True, "bonusAwarded": bonus_awarded})


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.all().order_by("-created_at")


class GrantAdminView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=None,
        responses={200: AdminUserSerializer, 404: OpenApiTypes.OBJECT},
        description="Grant admin privileges to the target user.",
    )
    def post(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            _sync_firebase_admin_claim(user.id)
        except Exception as exc:
            logger.exception("Failed to sync Firebase admin claim for user=%s: %s", user.id, exc)
            return Response(
                {"error": "Failed to sync Firebase admin claim."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not user.is_admin:
            user.is_admin = True
            user.save(update_fields=["is_admin", "updated_at"])

        return Response(AdminUserSerializer(user).data)
