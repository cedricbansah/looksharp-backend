import uuid

from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from apps.offers.models import Offer
from apps.surveys.models import Survey
from services.r2 import upload_file

from .models import Client
from .serializers import ClientCreateSerializer, ClientSerializer, ClientUpdateSerializer

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


class AdminClientListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return Client.objects.all().order_by("name")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClientCreateSerializer
        return ClientSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save(id=str(uuid.uuid4()))
        return Response(ClientSerializer(client).data, status=status.HTTP_201_CREATED)


class AdminClientUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientUpdateSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ClientSerializer(client).data)

    def delete(self, request, client_id):
        with transaction.atomic():
            client = Client.objects.select_for_update().filter(id=client_id).first()
            if not client:
                return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

            linked_survey = Survey.objects.filter(client_id=client.id).exists()
            linked_offer = Offer.objects.filter(client_id=client.id).exists()
            if linked_survey or linked_offer:
                return Response(
                    {"error": "Cannot delete client referenced by surveys or offers."},
                    status=status.HTTP_409_CONFLICT,
                )

            client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminClientLogoUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "file is required."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (file_obj.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            return Response(
                {"error": "Unsupported image type. Allowed: jpeg, png, webp."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > MAX_UPLOAD_SIZE_BYTES:
            return Response(
                {"error": "File size must be 5MB or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key = f"clients/{client.id}/logo"
        logo_url = upload_file(file_obj, key=key, content_type=content_type)
        client.logo_url = logo_url
        client.save(update_fields=["logo_url", "updated_at"])

        return Response(ClientSerializer(client).data)
