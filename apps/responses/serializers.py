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

    def validate_survey_id(self, value):
        if not Survey.objects.filter(id=value).exists():
            raise serializers.ValidationError("Survey does not exist.")
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
        survey = Survey.objects.filter(id=validated_data["survey_id"]).only("points").first()
        if not survey:
            raise serializers.ValidationError({"survey_id": "Survey does not exist."})
        validated_data["points_earned"] = survey.points
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
