import uuid

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin
from services.r2 import upload_file

from .models import Client
from .serializers import ClientCreateSerializer, ClientSerializer, ClientUpdateSerializer

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


def _detected_image_content_type(file_obj):
    header = file_obj.read(12)
    file_obj.seek(0)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


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

    @extend_schema(
        request=ClientUpdateSerializer,
        responses={
            200: ClientSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Update an existing client.",
    )
    def patch(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientUpdateSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ClientSerializer(client).data)

    @extend_schema(
        request=None,
        responses={
            204: None,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        description="Delete a client if it is not referenced by surveys or offers.",
    )
    def delete(self, request, client_id):
        with transaction.atomic():
            client = Client.objects.select_for_update().filter(id=client_id).first()
            if not client:
                return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

            linked_survey = client.surveys.exists()
            linked_offer = client.offers.exists()
            if linked_survey or linked_offer:
                return Response(
                    {"error": "Cannot delete client referenced by surveys or offers."},
                    status=status.HTTP_409_CONFLICT,
                )

            client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminClientLogoUploadView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        request=inline_serializer(
            name="AdminClientLogoUploadRequest",
            fields={"file": serializers.ImageField()},
        ),
        responses={
            200: ClientSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description="Upload and attach a client logo image (multipart/form-data).",
    )
    def post(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"error": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "file is required."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (file_obj.content_type or "").lower()
        detected_type = _detected_image_content_type(file_obj)
        if detected_type not in ALLOWED_IMAGE_TYPES:
            return Response(
                {"error": "Invalid image file. Allowed: jpeg, png, webp."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if content_type and content_type != detected_type:
            return Response(
                {"error": "File content does not match provided content type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if file_obj.size > MAX_UPLOAD_SIZE_BYTES:
            return Response(
                {"error": "File size must be 5MB or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        key = f"clients/{client.id}/logo"
        logo_url = upload_file(file_obj, key=key, content_type=detected_type)
        client.logo_url = logo_url
        client.save(update_fields=["logo_url", "updated_at"])

        return Response(ClientSerializer(client).data)
