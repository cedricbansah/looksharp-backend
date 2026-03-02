from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse

from apps.core.permissions import IsVerified

from .models import Withdrawal
from .serializers import WithdrawalCreateSerializer, WithdrawalListSerializer


class WithdrawalListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/withdrawals/  - create a pending withdrawal (user must be verified)
    GET  /api/v1/withdrawals/  - list the authenticated user's withdrawals
    """

    permission_classes = [IsAuthenticated, IsVerified]

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
        withdrawal = serializer.save(user_id=request.user.id, status="pending")
        return DRFResponse(
            WithdrawalListSerializer(withdrawal).data,
            status=status.HTTP_201_CREATED,
        )
