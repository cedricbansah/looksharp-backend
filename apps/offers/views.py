import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdmin
from apps.users.models import User
from services.r2 import upload_file

from .models import Offer, Redemption
from .serializers import (
    AdminOfferCreateSerializer,
    AdminOfferUpdateSerializer,
    OfferListSerializer,
    RedemptionCreateSerializer,
    RedemptionListSerializer,
)

logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


def _detected_image_content_type(file_obj):
    header = file_obj.read(12)
    file_obj.seek(0)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class OfferListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OfferListSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            Offer.objects.filter(status="active")
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .select_related("client")
            .order_by("-created_at")
        )


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
            now = timezone.now()
            try:
                offer = (
                    Offer.objects.select_for_update()
                    .filter(
                        id=offer_id,
                        status="active",
                    )
                    .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
                    .get()
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

            try:
                redemption = Redemption.objects.create(
                    user_id=user.id,
                    offer=offer,
                    offer_code=offer.offer_code,
                    offer_title=offer.title,
                    client_name=offer.client.name if offer.client else "",
                )
            except IntegrityError:
                # Idempotency on (user_id, offer_id): return existing redemption.
                redemption = Redemption.objects.get(user_id=user.id, offer_id=offer.id)
                return Response(RedemptionListSerializer(redemption).data, status=status.HTTP_200_OK)

            User.objects.filter(id=user.id).update(
                offers_claimed=user.offers_claimed + [offer.id],
            )

            logger.info(
                "Offer redeemed: user=%s offer=%s",
                user.id,
                offer.id,
            )

        return Response(
            RedemptionListSerializer(redemption).data,
            status=status.HTTP_201_CREATED,
        )


class AdminOfferListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return Offer.objects.all().select_related("client").order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminOfferCreateSerializer
        return OfferListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = serializer.save()
        return Response(OfferListSerializer(offer).data, status=status.HTTP_201_CREATED)


class AdminOfferUpdateDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Offer.objects.all()
    serializer_class = AdminOfferUpdateSerializer

    @extend_schema(
        request=AdminOfferUpdateSerializer,
        responses={
            200: OfferListSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Update an existing offer.",
    )
    def patch(self, request, offer_id):
        offer = self.get_queryset().filter(id=offer_id).first()
        if not offer:
            return Response({"error": "Offer not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminOfferUpdateSerializer(offer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OfferListSerializer(offer).data)

    @extend_schema(
        request=None,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        description="Delete an offer if it has no redemptions.",
    )
    def delete(self, request, offer_id):
        with transaction.atomic():
            offer = Offer.objects.select_for_update().filter(id=offer_id).first()
            if not offer:
                return Response({"error": "Offer not found."}, status=status.HTTP_404_NOT_FOUND)

            has_redemptions = Redemption.objects.select_for_update().filter(offer_id=offer.id).exists()
            if has_redemptions:
                return Response(
                    {"error": "Cannot delete an offer with existing redemptions."},
                    status=status.HTTP_409_CONFLICT,
                )

            offer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOfferPosterUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    queryset = Offer.objects.all()
    serializer_class = OfferListSerializer

    @extend_schema(
        request=inline_serializer(
            name="AdminOfferPosterUploadRequest",
            fields={"file": serializers.ImageField()},
        ),
        responses={
            200: OfferListSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Upload and attach an offer poster image (multipart/form-data).",
    )
    def post(self, request, offer_id):
        offer = self.get_queryset().filter(id=offer_id).first()
        if not offer:
            return Response({"error": "Offer not found."}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "file is required."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (file_obj.content_type or "").lower()
        detected_type = _detected_image_content_type(file_obj)
        if detected_type not in ALLOWED_IMAGE_TYPES:
            return Response(
                {"error": "Invalid image file. Allowed: jpeg, png, webp."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if content_type and content_type != detected_type:
            return Response(
                {"error": "File content does not match provided content type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > MAX_UPLOAD_SIZE_BYTES:
            return Response(
                {"error": "File size must be 5MB or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key = f"offers/{offer.id}/poster"
        poster_url = upload_file(file_obj, key=key, content_type=detected_type)
        offer.poster_url = poster_url
        offer.save(update_fields=["poster_url", "updated_at"])

        return Response(OfferListSerializer(offer).data, status=status.HTTP_200_OK)
