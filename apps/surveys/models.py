from django.db import models


class Survey(models.Model):
    id = models.CharField(max_length=128, primary_key=True)  # Firestore doc ID
    title = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, default="draft")
    points = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "surveys"

    def __str__(self):
        return self.title or self.id
