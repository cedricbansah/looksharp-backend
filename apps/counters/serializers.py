from rest_framework import serializers

from .models import DashboardCounter


class DashboardCounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardCounter
        fields = [
            "active_surveys",
            "total_responses",
            "active_offers",
            "total_users",
            "verified_users",
            "total_points_issued",
            "total_paid_out",
            "pending_verifications",
            "pending_withdrawals",
            "updated_at",
        ]
        read_only_fields = fields
