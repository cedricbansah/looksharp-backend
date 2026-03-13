from django.db.models import Q
from rest_framework import serializers

from apps.clients.models import Client

from .models import Offer, OfferCategory, Redemption


def _validate_offer_category(value: str) -> str:
    if not value:
        return value
    exists = OfferCategory.objects.filter(Q(id=value) | Q(name=value)).exists()
    if not exists:
        raise serializers.ValidationError("Unknown offer category.")
    return value


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
    offer_code = serializers.CharField(read_only=True)

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
            "end_date",
            "is_featured",
        ]

    def validate(self, attrs):
        if "offer_code" in self.initial_data:
            raise serializers.ValidationError(
                {"offer_code": "offer_code is inherited from the selected client and cannot be set manually."}
            )
        if "category" in attrs:
            attrs["category"] = _validate_offer_category(attrs["category"])
        return super().validate(attrs)

    def create(self, validated_data):
        client = validated_data.get("client")
        validated_data["offer_code"] = (client.client_code or "") if client else ""
        return super().create(validated_data)


class AdminOfferUpdateSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.objects.all(),
        allow_null=True,
        required=False,
    )
    offer_code = serializers.CharField(read_only=True)

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
            "end_date",
            "is_featured",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate(self, attrs):
        if "offer_code" in self.initial_data:
            raise serializers.ValidationError(
                {"offer_code": "offer_code is inherited from the selected client and cannot be set manually."}
            )
        if "category" in attrs:
            attrs["category"] = _validate_offer_category(attrs["category"])
        return super().validate(attrs)

    def update(self, instance, validated_data):
        if "client" in validated_data:
            client = validated_data.get("client")
            validated_data["offer_code"] = (client.client_code or "") if client else ""
        return super().update(instance, validated_data)


class OfferCategorySerializer(serializers.ModelSerializer):
    offer_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = OfferCategory
        fields = [
            "id",
            "name",
            "icon",
            "offer_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OfferCategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCategory
        fields = [
            "name",
            "icon",
        ]


class OfferCategoryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCategory
        fields = [
            "name",
            "icon",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}
