from rest_framework import serializers

from .models import Client


def _normalized_client_code(value):
    if value in {"", None}:
        return None
    return value


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "website_url",
            "description",
            "client_code",
            "logo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ClientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "name",
            "email",
            "phone",
            "address",
            "website_url",
            "description",
            "client_code",
            "logo_url",
        ]

    def validate_client_code(self, value):
        value = _normalized_client_code(value)
        if value and Client.objects.filter(client_code=value).exists():
            raise serializers.ValidationError("A client with this client_code already exists.")
        return value


class ClientUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "name",
            "email",
            "phone",
            "address",
            "website_url",
            "description",
            "client_code",
            "logo_url",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_client_code(self, value):
        value = _normalized_client_code(value)
        if self.instance and value != self.instance.client_code:
            raise serializers.ValidationError("client_code is immutable once set.")
        return value
