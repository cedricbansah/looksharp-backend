import uuid

from django.db import models
from django.utils import timezone


VERIFICATION_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]

NETWORK_PROVIDER_CHOICES = [
    ("MTN", "MTN"),
    ("Telecel", "Telecel"),
    ("ATMoney", "ATMoney"),
]

ID_TYPE_CHOICES = [
    ("ghana_card", "Ghana Card"),
    ("passport", "Passport"),
    ("voter_id", "Voter ID"),
    ("drivers_license", "Drivers License"),
]


class Verification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True)
    full_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=32, blank=True)
    nationality = models.CharField(max_length=64, blank=True)
    mobile_number = models.CharField(max_length=32)
    network_provider = models.CharField(max_length=32, choices=NETWORK_PROVIDER_CHOICES)
    id_type = models.CharField(max_length=32, choices=ID_TYPE_CHOICES)
    id_number = models.CharField(max_length=128)
    id_front_url = models.URLField(max_length=500)
    id_back_url = models.URLField(max_length=500)
    selfie_url = models.URLField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.CharField(max_length=128, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "verifications"
        indexes = [
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["user_id", "status", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.status}"
