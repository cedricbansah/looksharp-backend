from rest_framework import serializers

from .models import Offer, Redemption


class OfferListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = [
            "id",
            "title",
            "description",
            "status",
            "category",
            "url",
            "poster_url",
            "client_id",
            "client_name",
            "client_logo_url",
            "offer_code",
            "points_required",
            "end_date",
            "days_remaining",
            "is_featured",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RedemptionCreateSerializer(serializers.Serializer):
    offer_id = serializers.CharField(max_length=128)


class RedemptionListSerializer(serializers.ModelSerializer):
    offer_id = serializers.CharField(source="offer.id", read_only=True)

    class Meta:
        model = Redemption
        fields = [
            "id",
            "user_id",
            "offer_id",
            "offer_code",
            "offer_title",
            "client_name",
            "points_spent",
            "redeemed_at",
        ]
        read_only_fields = fields
