import uuid

from django.db import transaction
from django.db.models import Case, F, Max, Q, Value, When
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.responses.models import Response as SurveyResponse

from .models import Question, Survey, SurveyCategory
from .serializers import (
    AdminQuestionCreateSerializer,
    AdminQuestionUpdateSerializer,
    AdminSurveyCreateSerializer,
    AdminSurveyUpdateSerializer,
    QuestionReorderSerializer,
    QuestionSerializer,
    SurveyCategoryCreateSerializer,
    SurveyCategorySerializer,
    SurveyCategoryUpdateSerializer,
    SurveyDetailSerializer,
    SurveyListSerializer,
)


def _survey_category_filter(category: SurveyCategory) -> Q:
    return Q(category=category.id) | Q(category=category.name)


class SurveyListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SurveyListSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            Survey.objects.filter(status="active")
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .select_related("client")
            .order_by("-created_at")
        )


class SurveyDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SurveyDetailSerializer

    def get_queryset(self):
        now = timezone.now()
        return (
            Survey.objects.filter(status="active")
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .select_related("client")
        )


class AdminSurveyListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return Survey.objects.all().select_related("client").order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminSurveyCreateSerializer
        return SurveyListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = serializer.save(
            id=str(uuid.uuid4()),
            question_count=0,
            response_count=0,
        )
        return Response(SurveyListSerializer(survey).data, status=status.HTTP_201_CREATED)


class AdminSurveyUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=AdminSurveyUpdateSerializer,
        responses={
            200: SurveyListSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Update an existing survey.",
    )
    def patch(self, request, survey_id):
        survey = Survey.objects.filter(id=survey_id).first()
        if not survey:
            return Response({"error": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminSurveyUpdateSerializer(survey, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SurveyListSerializer(survey).data)

    @extend_schema(
        request=None,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        description="Delete a survey if it has no existing responses.",
    )
    def delete(self, request, survey_id):
        with transaction.atomic():
            survey = Survey.objects.select_for_update().filter(id=survey_id).first()
            if not survey:
                return Response({"error": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)

            if SurveyResponse.objects.filter(survey_id=survey.id).exists():
                return Response(
                    {"error": "Cannot delete a survey with existing responses."},
                    status=status.HTTP_409_CONFLICT,
                )

            survey.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminQuestionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return Question.objects.filter(survey_id=self.kwargs["survey_id"]).order_by(
            "position_index", "created_at"
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminQuestionCreateSerializer
        return QuestionSerializer

    def create(self, request, *args, **kwargs):
        survey = Survey.objects.filter(id=self.kwargs["survey_id"]).first()
        if not survey:
            return Response({"error": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            max_position = (
                Question.objects.filter(survey_id=survey.id).aggregate(max_position=Max("position_index"))[
                    "max_position"
                ]
                or 0
            )
            question = serializer.save(
                id=str(uuid.uuid4()),
                survey=survey,
                position_index=max_position + 1,
            )
            Survey.objects.filter(id=survey.id).update(question_count=F("question_count") + 1)

        return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)


class AdminQuestionUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=AdminQuestionUpdateSerializer,
        responses={
            200: QuestionSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Update a question in a survey.",
    )
    def patch(self, request, survey_id, question_id):
        question = Question.objects.filter(id=question_id, survey_id=survey_id).first()
        if not question:
            return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminQuestionUpdateSerializer(question, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(QuestionSerializer(question).data)

    @extend_schema(
        request=None,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
        },
        description="Delete a question from a survey.",
    )
    def delete(self, request, survey_id, question_id):
        with transaction.atomic():
            question = Question.objects.select_for_update().filter(id=question_id, survey_id=survey_id).first()
            if not question:
                return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

            question.delete()
            Survey.objects.filter(id=survey_id).update(
                question_count=Case(
                    When(question_count__gt=0, then=F("question_count") - 1),
                    default=Value(0),
                )
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminQuestionReorderView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=QuestionReorderSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Swap order of two questions in a survey.",
    )
    def post(self, request, survey_id):
        survey_exists = Survey.objects.filter(id=survey_id).exists()
        if not survey_exists:
            return Response({"error": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = QuestionReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            question_a = (
                Question.objects.select_for_update()
                .filter(
                    id=serializer.validated_data["question_a_id"],
                    survey_id=survey_id,
                )
                .first()
            )
            question_b = (
                Question.objects.select_for_update()
                .filter(
                    id=serializer.validated_data["question_b_id"],
                    survey_id=survey_id,
                )
                .first()
            )
            if not question_a or not question_b:
                return Response(
                    {"error": "Both questions must exist in the survey."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            question_a.position_index, question_b.position_index = (
                question_b.position_index,
                question_a.position_index,
            )
            question_a.save(update_fields=["position_index", "updated_at"])
            question_b.save(update_fields=["position_index", "updated_at"])

        return Response({"success": True}, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(
        request=SurveyCategoryCreateSerializer,
        responses={
            201: SurveyCategorySerializer,
            400: OpenApiTypes.OBJECT,
        },
        description="Create a new survey category.",
    )
)
class AdminSurveyCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return SurveyCategory.objects.all().order_by("name")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        categories = page if page is not None else queryset
        data = []
        for category in categories:
            payload = SurveyCategorySerializer(category).data
            payload["survey_count"] = Survey.objects.filter(_survey_category_filter(category)).count()
            data.append(payload)
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SurveyCategoryCreateSerializer
        return SurveyCategorySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save(id=str(uuid.uuid4()))
        payload = SurveyCategorySerializer(category).data
        payload["survey_count"] = 0
        return Response(payload, status=status.HTTP_201_CREATED)


class AdminSurveyCategoryUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=SurveyCategoryUpdateSerializer,
        responses={
            200: SurveyCategorySerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Update an existing survey category.",
    )
    def patch(self, request, category_id):
        category = SurveyCategory.objects.filter(id=category_id).first()
        if not category:
            return Response({"error": "Survey category not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SurveyCategoryUpdateSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        payload = SurveyCategorySerializer(category).data
        payload["survey_count"] = Survey.objects.filter(_survey_category_filter(category)).count()
        return Response(payload)

    @extend_schema(
        request=None,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        description="Delete a survey category if it is not referenced by surveys.",
    )
    def delete(self, request, category_id):
        with transaction.atomic():
            category = SurveyCategory.objects.select_for_update().filter(id=category_id).first()
            if not category:
                return Response({"error": "Survey category not found."}, status=status.HTTP_404_NOT_FOUND)

            if Survey.objects.filter(_survey_category_filter(category)).exists():
                return Response(
                    {"error": "Cannot delete survey category referenced by surveys."},
                    status=status.HTTP_409_CONFLICT,
                )

            category.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
