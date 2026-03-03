from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin

from .models import DashboardCounter
from .serializers import DashboardCounterSerializer
from .tasks import (
    recompute_active_offers,
    recompute_active_surveys,
    recompute_extended_dashboard,
    recompute_total_paid_out,
    recompute_total_responses,
)


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=None,
        responses={200: DashboardCounterSerializer},
        description="Fetch admin dashboard counters.",
    )
    def get(self, request):
        counter, _ = DashboardCounter.objects.get_or_create(id="dashboard")
        return Response(DashboardCounterSerializer(counter).data)


class AdminCounterRebuildView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=None,
        responses={202: OpenApiTypes.OBJECT},
        description="Dispatch asynchronous counter recompute tasks.",
    )
    def post(self, request):
        recompute_active_surveys.delay()
        recompute_active_offers.delay()
        recompute_total_responses.delay()
        recompute_total_paid_out.delay()
        recompute_extended_dashboard.delay()
        return Response(
            {"success": True, "message": "Counter recompute tasks dispatched."},
            status=status.HTTP_202_ACCEPTED,
        )
