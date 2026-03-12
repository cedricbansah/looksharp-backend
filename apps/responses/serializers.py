from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.surveys.models import Survey

from .models import Response


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    question_text = serializers.CharField(allow_blank=True, default="")
    position_index = serializers.IntegerField(default=0)
    answer_text = serializers.CharField(allow_blank=True, default="")


class ResponseCreateSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)
    user_id = serializers.CharField(required=False, write_only=True)
    user_email = serializers.EmailField(required=False, write_only=True)
    points_earned = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = Response
        fields = [
            "survey_id",
            "survey_title",
            "user_id",
            "user_email",
            "points_earned",
            "submitted_at",
            "answers",
        ]
        validators = []

    def validate_survey_id(self, value):
        now = timezone.now()
        if not Survey.objects.filter(id=value, status="active").filter(
            Q(end_date__isnull=True) | Q(end_date__gt=now)
        ).exists():
            raise serializers.ValidationError("Survey does not exist or is not active.")
        return value

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("answers must not be empty.")
        return value

    def validate(self, attrs):
        attrs.pop("user_id", None)
        attrs.pop("user_email", None)
        attrs.pop("points_earned", None)
        return attrs

    def create(self, validated_data):
        now = timezone.now()
        survey = (
            Survey.objects.filter(id=validated_data["survey_id"], status="active")
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .only("points", "title")
            .first()
        )
        if not survey:
            raise serializers.ValidationError({"survey_id": "Survey does not exist or is not active."})
        validated_data["points_earned"] = survey.points
        validated_data["survey_title"] = survey.title or ""
        return super().create(validated_data)


class ResponseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = [
            "id",
            "survey_id",
            "survey_title",
            "user_id",
            "user_email",
            "points_earned",
            "submitted_at",
            "answers",
            "created_at",
        ]
        read_only_fields = fields
