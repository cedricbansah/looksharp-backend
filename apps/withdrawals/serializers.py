from decimal import Decimal

from rest_framework import serializers

from .models import Withdrawal

MINIMUM_AMOUNT_GHS = Decimal("5.00")


class WithdrawalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "amount_ghs",
            "points_converted",
        ]

    def validate_amount_ghs(self, value):
        if value < MINIMUM_AMOUNT_GHS:
            raise serializers.ValidationError(
                f"Minimum withdrawal amount is GHS {MINIMUM_AMOUNT_GHS}."
            )
        return value

    def validate_points_converted(self, value):
        if value <= 0:
            raise serializers.ValidationError("points_converted must be greater than 0.")
        return value


class WithdrawalListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "user_id",
            "amount_ghs",
            "points_converted",
            "recipient_code",
            "transfer_reference",
            "transfer_code",
            "status",
            "failure_reason",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields


class AdminWithdrawalUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["failed", "completed"])
    failure_reason = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        if attrs["status"] == "failed" and not attrs.get("failure_reason"):
            raise serializers.ValidationError({"failure_reason": "failure_reason is required for failed status."})
        return attrs
