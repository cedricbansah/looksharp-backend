import logging

import requests as http_requests
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import services.paystack as paystack_service

logger = logging.getLogger(__name__)


class BanksView(APIView):
    """GET /api/v1/paystack/banks/ - list telcos/banks"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = paystack_service.list_banks(
                type=request.query_params.get("type", "mobile_money"),
                currency=request.query_params.get("currency", "GHS"),
            )
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
        try:
            data = paystack_service.create_transfer_recipient(
                name=request.data["name"],
                account_number=request.data["account_number"],
                bank_code=request.data["bank_code"],
                type=request.data.get("type", "mobile_money"),
                currency=request.data.get("currency", "GHS"),
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except KeyError as exc:
            return Response(
                {"error": f"Missing field: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        try:
            data = paystack_service.initiate_transfer(
                recipient=request.data["recipient"],
                amount_kobo=request.data["amount"],
                reference=request.data["reference"],
                reason=request.data.get("reason", "LookSharp cashout"),
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except KeyError as exc:
            return Response(
                {"error": f"Missing field: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        try:
            data = paystack_service.finalize_transfer(transfer_code)
            return Response(data)
        except http_requests.HTTPError as exc:
            logger.error("Paystack finalize_transfer failed: %s", exc)
            return Response(
                {"error": "Paystack request failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
