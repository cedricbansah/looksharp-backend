from rest_framework import serializers

from .models import Response


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    question_text = serializers.CharField(allow_blank=True, default="")
    position_index = serializers.IntegerField(default=0)
    answer_text = serializers.CharField(allow_blank=True, default="")


class ResponseCreateSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)

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

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("answers must not be empty.")
        return value


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
            "is_deleted",
            "created_at",
        ]
        read_only_fields = fields
