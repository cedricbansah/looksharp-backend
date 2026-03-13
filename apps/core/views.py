from django.db import connection
from django.http import JsonResponse
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.offers.models import OFFER_STATUS_CHOICES, Offer, OfferCategory
from apps.surveys.models import QUESTION_TYPE_CHOICES, SURVEY_STATUS_CHOICES, Survey, SurveyCategory
from apps.verifications.models import (
    ID_TYPE_CHOICES,
    NETWORK_PROVIDER_CHOICES,
    VERIFICATION_STATUS_CHOICES,
)
from apps.withdrawals.models import WITHDRAWAL_STATUS_CHOICES

from .serializers import ConfigEnumsResponseSerializer

GENDER_OPTIONS = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]


def _serialize_choices(choices):
    return [{"value": value, "label": label} for value, label in choices]


def _survey_category_filter(category: SurveyCategory) -> Q:
    return Q(category=category.id) | Q(category=category.name)


def _offer_category_filter(category: OfferCategory) -> Q:
    return Q(category=category.id) | Q(category=category.name)


def health_check(request):
    """
    Health check endpoint for load balancers and orchestrators.
    Returns 200 if the app can connect to the database.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "healthy", "database": "connected"})
    except Exception as e:
        return JsonResponse(
            {"status": "unhealthy", "database": "disconnected", "error": str(e)},
            status=503,
        )


class ConfigEnumsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: ConfigEnumsResponseSerializer},
        auth=[],
        description="Return backend-owned enum options and category configuration for clients.",
    )
    def get(self, request):
        survey_categories = []
        for category in SurveyCategory.objects.all().order_by("name"):
            survey_categories.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "icon": category.icon,
                    "survey_count": Survey.objects.filter(_survey_category_filter(category)).count(),
                }
            )

        offer_categories = []
        for category in OfferCategory.objects.all().order_by("name"):
            offer_categories.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "icon": category.icon,
                    "offer_count": Offer.objects.filter(_offer_category_filter(category)).count(),
                }
            )

        payload = {
            "survey_statuses": _serialize_choices(SURVEY_STATUS_CHOICES),
            "question_types": _serialize_choices(QUESTION_TYPE_CHOICES),
            "offer_statuses": _serialize_choices(OFFER_STATUS_CHOICES),
            "verification_statuses": _serialize_choices(VERIFICATION_STATUS_CHOICES),
            "withdrawal_statuses": _serialize_choices(WITHDRAWAL_STATUS_CHOICES),
            "network_providers": _serialize_choices(NETWORK_PROVIDER_CHOICES),
            "id_types": _serialize_choices(ID_TYPE_CHOICES),
            "genders": _serialize_choices(GENDER_OPTIONS),
            "survey_categories": survey_categories,
            "offer_categories": offer_categories,
        }
        response = Response(ConfigEnumsResponseSerializer(payload).data)
        response["Cache-Control"] = "public, max-age=3600"
        return response
