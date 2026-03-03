from django.db import models


class DashboardCounter(models.Model):
    id = models.CharField(max_length=32, primary_key=True, default="dashboard")
    active_surveys = models.PositiveIntegerField(default=0)
    total_responses = models.PositiveIntegerField(default=0)
    active_offers = models.PositiveIntegerField(default=0)
    total_users = models.PositiveIntegerField(default=0)
    verified_users = models.PositiveIntegerField(default=0)
    total_points_issued = models.PositiveIntegerField(default=0)
    total_paid_out = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_verifications = models.PositiveIntegerField(default=0)
    pending_withdrawals = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_counters"

    def __str__(self):
        return self.id
