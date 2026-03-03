# Generated manually for Phase 3

from django.db import migrations, models
import django.db.models.deletion
import uuid

import apps.offers.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Offer",
            fields=[
                ("id", models.CharField(default=apps.offers.models._offer_id, max_length=128, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("description", models.CharField(blank=True, max_length=1000)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("inactive", "Inactive")],
                        default="inactive",
                        max_length=20,
                    ),
                ),
                ("category", models.CharField(blank=True, max_length=100)),
                ("url", models.URLField(blank=True)),
                ("poster_url", models.URLField(blank=True)),
                ("client_id", models.CharField(blank=True, max_length=128)),
                ("client_name", models.CharField(blank=True, max_length=255)),
                ("client_logo_url", models.URLField(blank=True)),
                ("offer_code", models.CharField(blank=True, db_index=True, max_length=64)),
                ("points_required", models.PositiveIntegerField(default=0)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("days_remaining", models.PositiveIntegerField(default=0)),
                ("is_featured", models.BooleanField(default=False)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "offers",
            },
        ),
        migrations.CreateModel(
            name="Redemption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.CharField(db_index=True, max_length=128)),
                ("offer_code", models.CharField(blank=True, max_length=64)),
                ("offer_title", models.CharField(blank=True, max_length=200)),
                ("client_name", models.CharField(blank=True, max_length=255)),
                ("points_spent", models.PositiveIntegerField(default=0)),
                ("redeemed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "offer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="redemptions", to="offers.offer"),
                ),
            ],
            options={
                "db_table": "redemptions",
                "unique_together": {("user_id", "offer")},
            },
        ),
        migrations.AddIndex(
            model_name="offer",
            index=models.Index(fields=["is_deleted", "status", "-created_at"], name="offers_offer_is_dele_75bfa7_idx"),
        ),
        migrations.AddIndex(
            model_name="offer",
            index=models.Index(fields=["is_deleted", "category", "-created_at"], name="offers_offer_is_dele_40ba95_idx"),
        ),
        migrations.AddIndex(
            model_name="redemption",
            index=models.Index(fields=["user_id", "-redeemed_at"], name="redemptions_user_id_79b0ca_idx"),
        ),
        migrations.AddIndex(
            model_name="redemption",
            index=models.Index(fields=["offer", "-redeemed_at"], name="redemptions_offer_i_5fd582_idx"),
        ),
    ]
