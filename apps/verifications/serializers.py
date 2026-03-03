from django.utils import timezone
from rest_framework import serializers

from .models import Verification


class VerificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = [
            "full_name",
            "gender",
            "nationality",
            "mobile_number",
            "network_provider",
            "id_type",
            "id_number",
            "id_front_url",
            "id_back_url",
            "selfie_url",
        ]

    def create(self, validated_data):
        validated_data["submitted_at"] = timezone.now()
        validated_data["status"] = "pending"
        return super().create(validated_data)


class VerificationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = [
            "id",
            "user_id",
            "full_name",
            "gender",
            "nationality",
            "mobile_number",
            "network_provider",
            "id_type",
            "id_number",
            "id_front_url",
            "id_back_url",
            "selfie_url",
            "status",
            "rejection_reason",
            "reviewed_by",
            "reviewed_at",
            "submitted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VerificationRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(max_length=1000)
