import uuid

from django.db import models


OFFER_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
]


def _offer_id() -> str:
    return str(uuid.uuid4())


class Offer(models.Model):
    id = models.CharField(max_length=128, primary_key=True, default=_offer_id)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=OFFER_STATUS_CHOICES, default="inactive")
    category = models.CharField(max_length=100, blank=True)
    url = models.URLField(blank=True, max_length=500)
    poster_url = models.URLField(blank=True, max_length=500)
    client = models.ForeignKey(
        "clients.Client",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="offers",
    )
    offer_code = models.CharField(max_length=64, blank=True, db_index=True)
    points_required = models.PositiveIntegerField(default=0)
    end_date = models.DateTimeField(null=True, blank=True)
    days_remaining = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "offers"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return self.title


class Redemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="redemptions")
    offer_code = models.CharField(max_length=64, blank=True)
    offer_title = models.CharField(max_length=200, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    points_spent = models.PositiveIntegerField(default=0)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "redemptions"
        unique_together = [("user_id", "offer")]
        indexes = [
            models.Index(fields=["user_id", "-redeemed_at"]),
            models.Index(fields=["offer", "-redeemed_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.offer_id}"
