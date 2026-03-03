from django.db import transaction
from django.db.models import F
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

WELCOME_BONUS_POINTS = 100


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
        return User.objects.filter(is_deleted=False).order_by("-created_at")


class GrantAdminView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, user_id):
        user = User.objects.filter(id=user_id, is_deleted=False).first()
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_admin:
            user.is_admin = True
            user.save(update_fields=["is_admin", "updated_at"])

        return Response(AdminUserSerializer(user).data)
