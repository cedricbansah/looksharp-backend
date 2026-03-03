from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Survey
from .serializers import SurveyDetailSerializer, SurveyListSerializer


class SurveyListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SurveyListSerializer

    def get_queryset(self):
        return Survey.objects.filter(
            status="active",
            is_deleted=False,
        ).order_by("-created_at")


class SurveyDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SurveyDetailSerializer

    def get_queryset(self):
        return Survey.objects.filter(
            status="active",
            is_deleted=False,
        )
