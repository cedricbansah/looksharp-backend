# Generated manually for Phase 3

from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Verification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=128)),
                ("full_name", models.CharField(max_length=255)),
                ("gender", models.CharField(blank=True, max_length=32)),
                ("nationality", models.CharField(blank=True, max_length=64)),
                ("mobile_number", models.CharField(max_length=32)),
                (
                    "network_provider",
                    models.CharField(
                        choices=[("MTN", "MTN"), ("Telecel", "Telecel"), ("ATMoney", "ATMoney")],
                        max_length=32,
                    ),
                ),
                (
                    "id_type",
                    models.CharField(
                        choices=[
                            ("ghana_card", "Ghana Card"),
                            ("passport", "Passport"),
                            ("voter_id", "Voter ID"),
                            ("drivers_license", "Drivers License"),
                        ],
                        max_length=32,
                    ),
                ),
                ("id_number", models.CharField(max_length=128)),
                ("id_front_url", models.URLField()),
                ("id_back_url", models.URLField()),
                ("selfie_url", models.URLField()),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("rejection_reason", models.TextField(blank=True)),
                ("reviewed_by", models.CharField(blank=True, max_length=128)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notification_sent", models.BooleanField(default=False)),
                ("notification_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "verifications",
            },
        ),
        migrations.AddIndex(
            model_name="verification",
            index=models.Index(fields=["status", "submitted_at"], name="verification_status_9ee794_idx"),
        ),
        migrations.AddIndex(
            model_name="verification",
            index=models.Index(fields=["user_id", "status", "submitted_at"], name="verification_user_id_d26b60_idx"),
        ),
    ]
