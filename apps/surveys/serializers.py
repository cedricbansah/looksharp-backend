from rest_framework import serializers

from .models import Question, Survey


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "survey",
            "question_text",
            "question_subtext",
            "question_type",
            "position_index",
            "choices",
            "scale_lower_limit",
            "scale_upper_limit",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SurveyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = [
            "id",
            "title",
            "description",
            "status",
            "category",
            "client_id",
            "client_name",
            "points",
            "question_count",
            "response_count",
            "estimated_time",
            "end_date",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SurveyDetailSerializer(SurveyListSerializer):
    questions = serializers.SerializerMethodField()

    class Meta(SurveyListSerializer.Meta):
        fields = [*SurveyListSerializer.Meta.fields, "questions"]
        read_only_fields = fields

    def get_questions(self, obj):
        queryset = obj.questions.filter(is_deleted=False).order_by("position_index", "created_at")
        return QuestionSerializer(queryset, many=True).data
