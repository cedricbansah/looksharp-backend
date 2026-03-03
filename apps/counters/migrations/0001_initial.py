# Generated manually for Phase 3

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DashboardCounter",
            fields=[
                ("id", models.CharField(default="dashboard", max_length=32, primary_key=True, serialize=False)),
                ("active_surveys", models.PositiveIntegerField(default=0)),
                ("total_responses", models.PositiveIntegerField(default=0)),
                ("active_offers", models.PositiveIntegerField(default=0)),
                ("total_users", models.PositiveIntegerField(default=0)),
                ("verified_users", models.PositiveIntegerField(default=0)),
                ("total_points_issued", models.PositiveIntegerField(default=0)),
                ("total_paid_out", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("pending_verifications", models.PositiveIntegerField(default=0)),
                ("pending_withdrawals", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "dashboard_counters",
            },
        ),
    ]
