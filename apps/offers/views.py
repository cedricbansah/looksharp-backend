import logging

from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User

from .models import Offer, Redemption
from .serializers import (
    OfferListSerializer,
    RedemptionCreateSerializer,
    RedemptionListSerializer,
)

logger = logging.getLogger(__name__)


class OfferListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OfferListSerializer

    def get_queryset(self):
        return Offer.objects.filter(status="active", is_deleted=False).order_by("-created_at")


class RedemptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Redemption.objects.filter(user_id=self.request.user.id).order_by("-redeemed_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RedemptionCreateSerializer
        return RedemptionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer_id = serializer.validated_data["offer_id"]

        with transaction.atomic():
            user = User.objects.select_for_update().get(id=request.user.id)
            try:
                offer = Offer.objects.select_for_update().get(
                    id=offer_id,
                    is_deleted=False,
                    status="active",
                )
            except Offer.DoesNotExist:
                return Response(
                    {"error": "Offer does not exist or is not active."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            existing_redemption = Redemption.objects.filter(
                user_id=user.id,
                offer_id=offer.id,
            ).first()
            if existing_redemption:
                return Response(
                    RedemptionListSerializer(existing_redemption).data,
                    status=status.HTTP_200_OK,
                )

            if offer.points_required > user.points:
                return Response(
                    {"error": "Insufficient points to redeem this offer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                redemption = Redemption.objects.create(
                    user_id=user.id,
                    offer=offer,
                    offer_code=offer.offer_code,
                    offer_title=offer.title,
                    client_name=offer.client_name,
                    points_spent=offer.points_required,
                )
            except IntegrityError:
                # Idempotency on (user_id, offer_id): return existing redemption.
                redemption = Redemption.objects.get(user_id=user.id, offer_id=offer.id)
                return Response(RedemptionListSerializer(redemption).data, status=status.HTTP_200_OK)

            User.objects.filter(id=user.id).update(
                points=F("points") - offer.points_required,
                offers_claimed=user.offers_claimed + [offer.id],
            )

            logger.info(
                "Offer redeemed: user=%s offer=%s points=%s",
                user.id,
                offer.id,
                offer.points_required,
            )

        return Response(
            RedemptionListSerializer(redemption).data,
            status=status.HTTP_201_CREATED,
        )
