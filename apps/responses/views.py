from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse

from apps.core.permissions import IsAdmin

from .models import Response
from .serializers import ResponseCreateSerializer, ResponseListSerializer
from .tasks import apply_side_effects


class ResponseListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/responses/  - submit a survey response
    GET  /api/v1/responses/  - list the authenticated user's responses
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Response.objects.filter(user_id=self.request.user.id).order_by("-submitted_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ResponseCreateSerializer
        return ResponseListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey_id = serializer.validated_data["survey_id"]

        if Response.objects.filter(user_id=request.user.id, survey_id=survey_id).exists():
            return DRFResponse(
                {"error": "Response already submitted for this survey."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            response_obj = serializer.save(
                user_id=request.user.id,
                user_email=request.user.email or "",
            )
        except IntegrityError:
            return DRFResponse(
                {"error": "Response already submitted for this survey."},
                status=status.HTTP_409_CONFLICT,
            )
        # Fire side-effects task asynchronously on the critical queue
        apply_side_effects.apply_async(
            args=[response_obj.survey_id, response_obj.user_id],
            queue="critical",
        )
        return DRFResponse(
            ResponseListSerializer(response_obj).data,
            status=status.HTTP_201_CREATED,
        )


class ResponseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ResponseListSerializer

    def get_queryset(self):
        return Response.objects.filter(user_id=self.request.user.id)


class AdminResponseListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = ResponseListSerializer

    def get_queryset(self):
        queryset = Response.objects.all()
        survey_id = self.request.query_params.get("survey_id")
        if survey_id:
            queryset = queryset.filter(survey_id=survey_id)
        return queryset.order_by("-submitted_at")


class AdminResponseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = ResponseListSerializer
    queryset = Response.objects.all()
