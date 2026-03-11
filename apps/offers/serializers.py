from rest_framework import serializers

from apps.clients.models import Client

from .models import Offer, Redemption


class OfferListSerializer(serializers.ModelSerializer):
    client_id = serializers.CharField(source="client.id", default="")
    client_name = serializers.CharField(source="client.name", default="")
    client_logo_url = serializers.URLField(source="client.logo_url", default="")

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


class AdminOfferCreateSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Offer
        fields = [
            "title",
            "description",
            "status",
            "category",
            "url",
            "poster_url",
            "client_id",
            "offer_code",
            "points_required",
            "end_date",
            "is_featured",
        ]


class AdminOfferUpdateSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Offer
        fields = [
            "title",
            "description",
            "status",
            "category",
            "url",
            "poster_url",
            "client_id",
            "offer_code",
            "points_required",
            "end_date",
            "is_featured",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}
