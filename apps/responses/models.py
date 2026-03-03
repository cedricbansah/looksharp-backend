import uuid

from django.db import models


class Response(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_id = models.CharField(max_length=128, db_index=True)
    survey_title = models.CharField(max_length=500, blank=True)
    user_id = models.CharField(max_length=128, db_index=True)
    user_email = models.EmailField(blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField()
    # Embedded answers array - matches Firestore contract exactly
    # [{question_id, question_text, position_index, answer_text}, ...]
    answers = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "responses"
        # DB-level safety net - task also checks surveys_completed for idempotency
        unique_together = [("user_id", "survey_id")]

    def __str__(self):
        return f"Response {self.id} - survey {self.survey_id} by {self.user_id}"
