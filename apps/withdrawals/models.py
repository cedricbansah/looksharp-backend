import uuid

from django.db import models

WITHDRAWAL_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("processing", "Processing"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]


class Withdrawal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True)
    amount_ghs = models.DecimalField(max_digits=10, decimal_places=2)
    points_converted = models.PositiveIntegerField()
    recipient_code = models.CharField(max_length=100)
    # Unique logical key - enforces idempotency at DB level
    transfer_reference = models.CharField(max_length=200, unique=True)
    transfer_code = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20, default="pending", choices=WITHDRAWAL_STATUS_CHOICES
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "withdrawals"
        indexes = [
            models.Index(fields=["user_id", "status"]),
        ]

    def __str__(self):
        return f"Withdrawal {self.id} - {self.status} - {self.amount_ghs} GHS"
