from rest_framework import serializers

from .models import User

# Fields the client is ALLOWED to update (backend contract §4.2)
CLIENT_WRITABLE_FIELDS = [
    "first_name",
    "last_name",
    "phone",
    "date_of_birth",
    "gender",
    "country",
    "profile_photo_url",
]

# Server-controlled fields - read-only in all client-facing serializers
SERVER_CONTROLLED_FIELDS = [
    "points",
    "is_verified",
    "recipient_code",
    "is_admin",
    "welcome_bonus_claimed",
    "surveys_completed",
    "offers_claimed",
]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            *CLIENT_WRITABLE_FIELDS,
            *SERVER_CONTROLLED_FIELDS,
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            *SERVER_CONTROLLED_FIELDS,
            "created_at",
            "updated_at",
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """PATCH /users/me/ - only client-writable fields accepted."""

    class Meta:
        model = User
        fields = CLIENT_WRITABLE_FIELDS

    def to_internal_value(self, data):
        # Ignore unexpected keys so server-controlled fields are effectively no-op.
        filtered = {key: value for key, value in data.items() if key in self.fields}
        return super().to_internal_value(filtered)


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_verified",
            "is_admin",
            "points",
            "recipient_code",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
