import logging

import requests as http_requests
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import services.paystack as paystack_service
from .serializers import (
    BanksQuerySerializer,
    FinalizeTransferPathSerializer,
    TransferCreateSerializer,
    TransferRecipientCreateSerializer,
)

logger = logging.getLogger(__name__)


class BanksView(APIView):
    """GET /api/v1/paystack/banks/ - list telcos/banks"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BanksQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            data = paystack_service.list_banks(**serializer.validated_data)
            return Response(data)
        except http_requests.HTTPError as exc:
            logger.error("Paystack list_banks failed: %s", exc)
            return Response(
                {"error": "Paystack request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class TransferRecipientsView(APIView):
    """POST /api/v1/paystack/transfer-recipients/ - create a transfer recipient"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TransferRecipientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = paystack_service.create_transfer_recipient(**serializer.validated_data)
            return Response(data, status=status.HTTP_201_CREATED)
        except http_requests.HTTPError as exc:
            logger.error("Paystack create_recipient failed: %s", exc)
            return Response(
                {"error": "Paystack request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class TransfersView(APIView):
    """POST /api/v1/paystack/transfers/ - initiate a transfer"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = paystack_service.initiate_transfer(
                recipient=serializer.validated_data["recipient"],
                amount_kobo=serializer.validated_data["amount"],
                reference=serializer.validated_data["reference"],
                reason=serializer.validated_data["reason"],
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except http_requests.HTTPError as exc:
            logger.error("Paystack initiate_transfer failed: %s", exc)
            return Response(
                {"error": "Paystack request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class FinalizeTransferView(APIView):
    """POST /api/v1/paystack/transfers/{code}/finalize/ - finalize a transfer"""

    permission_classes = [IsAuthenticated]

    def post(self, request, transfer_code):
        serializer = FinalizeTransferPathSerializer(data={"transfer_code": transfer_code})
        serializer.is_valid(raise_exception=True)
        try:
            data = paystack_service.finalize_transfer(
                serializer.validated_data["transfer_code"]
            )
            return Response(data)
        except http_requests.HTTPError as exc:
            logger.error("Paystack finalize_transfer failed: %s", exc)
            return Response(
                {"error": "Paystack request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
