import uuid

from django.db import models


SURVEY_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("completed", "Completed"),
]

QUESTION_TYPE_CHOICES = [
    ("text", "Text"),
    ("single_select", "Single Select"),
    ("multi_select", "Multi Select"),
    ("single_select_other", "Single Select + Text"),
    ("multi_select_other", "Multi Select + Text"),
    ("linear_scale", "Linear Scale"),
]


def _question_id() -> str:
    return str(uuid.uuid4())


class Survey(models.Model):
    id = models.CharField(max_length=128, primary_key=True)  # Firestore doc ID
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="draft", choices=SURVEY_STATUS_CHOICES)
    category = models.CharField(max_length=100, blank=True)
    client = models.ForeignKey(
        "clients.Client",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="surveys",
    )
    points = models.PositiveIntegerField(default=0)
    question_count = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    estimated_time = models.PositiveIntegerField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "surveys"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return self.title or self.id


class SurveyCategory(models.Model):
    id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    icon = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "survey_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Question(models.Model):
    id = models.CharField(max_length=128, primary_key=True, default=_question_id)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    question_text = models.CharField(max_length=500)
    question_subtext = models.CharField(max_length=200, blank=True)
    question_type = models.CharField(max_length=32, choices=QUESTION_TYPE_CHOICES, default="text")
    position_index = models.PositiveIntegerField(default=0)
    choices = models.JSONField(default=list, blank=True)
    scale_lower_limit = models.IntegerField(null=True, blank=True)
    scale_upper_limit = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "questions"
        indexes = [
            models.Index(fields=["survey", "position_index"]),
        ]

    def __str__(self):
        return f"{self.survey_id}:{self.position_index}"
