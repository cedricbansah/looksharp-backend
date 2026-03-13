from typing import Any

from drf_spectacular.utils import extend_schema_field
from django.db.models import Q
from rest_framework import serializers

from apps.clients.models import Client

from .models import Question, Survey, SurveyCategory


def _validate_survey_category(value: str) -> str:
    if not value:
        return value
    exists = SurveyCategory.objects.filter(Q(id=value) | Q(name=value)).exists()
    if not exists:
        raise serializers.ValidationError("Unknown survey category.")
    return value


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SurveyListSerializer(serializers.ModelSerializer):
    client_id = serializers.CharField(source="client.id", default="")
    client_name = serializers.CharField(source="client.name", default="")

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SurveyDetailSerializer(SurveyListSerializer):
    questions = serializers.SerializerMethodField()

    class Meta(SurveyListSerializer.Meta):
        fields = [*SurveyListSerializer.Meta.fields, "questions"]
        read_only_fields = fields

    @extend_schema_field(QuestionSerializer(many=True))
    def get_questions(self, obj) -> list[dict[str, Any]]:
        queryset = obj.questions.order_by("position_index", "created_at")
        return QuestionSerializer(queryset, many=True).data


class AdminSurveyCreateSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Survey
        fields = [
            "title",
            "description",
            "status",
            "category",
            "client_id",
            "points",
            "estimated_time",
            "end_date",
            "created_by",
        ]

    def validate_category(self, value):
        return _validate_survey_category(value)


class AdminSurveyUpdateSerializer(serializers.ModelSerializer):
    client_id = serializers.PrimaryKeyRelatedField(
        source="client",
        queryset=Client.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Survey
        fields = [
            "title",
            "description",
            "status",
            "category",
            "client_id",
            "points",
            "estimated_time",
            "end_date",
            "created_by",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate_category(self, value):
        return _validate_survey_category(value)


class AdminQuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "question_text",
            "question_subtext",
            "question_type",
            "choices",
            "scale_lower_limit",
            "scale_upper_limit",
        ]

    def validate(self, attrs):
        question_type = attrs.get("question_type", "text")
        choices = attrs.get("choices", [])
        lower = attrs.get("scale_lower_limit")
        upper = attrs.get("scale_upper_limit")

        if question_type in {"single_select", "multi_select", "single_select_other", "multi_select_other"}:
            if not isinstance(choices, list) or len(choices) == 0:
                raise serializers.ValidationError({"choices": "choices must be a non-empty array."})

        if question_type == "linear_scale":
            if lower is None or upper is None:
                raise serializers.ValidationError(
                    {"scale_lower_limit": "Both scale limits are required for linear_scale."}
                )
        return attrs


class AdminQuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "question_text",
            "question_subtext",
            "question_type",
            "choices",
            "scale_lower_limit",
            "scale_upper_limit",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate(self, attrs):
        question_type = attrs.get("question_type", getattr(self.instance, "question_type", "text"))
        choices = attrs.get("choices", getattr(self.instance, "choices", []))
        lower = attrs.get("scale_lower_limit", getattr(self.instance, "scale_lower_limit", None))
        upper = attrs.get("scale_upper_limit", getattr(self.instance, "scale_upper_limit", None))

        if question_type in {"single_select", "multi_select", "single_select_other", "multi_select_other"}:
            if not isinstance(choices, list) or len(choices) == 0:
                raise serializers.ValidationError({"choices": "choices must be a non-empty array."})

        if question_type == "linear_scale":
            if lower is None or upper is None:
                raise serializers.ValidationError(
                    {"scale_lower_limit": "Both scale limits are required for linear_scale."}
                )
        return attrs


class QuestionReorderSerializer(serializers.Serializer):
    question_a_id = serializers.CharField(max_length=128)
    question_b_id = serializers.CharField(max_length=128)

    def validate(self, attrs):
        if attrs["question_a_id"] == attrs["question_b_id"]:
            raise serializers.ValidationError("question_a_id and question_b_id must be different.")
        return attrs


class SurveyCategorySerializer(serializers.ModelSerializer):
    survey_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SurveyCategory
        fields = [
            "id",
            "name",
            "icon",
            "survey_count",
        ]
        read_only_fields = fields


class SurveyCategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyCategory
        fields = [
            "name",
            "icon",
        ]


class SurveyCategoryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyCategory
        fields = [
            "name",
            "icon",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}
