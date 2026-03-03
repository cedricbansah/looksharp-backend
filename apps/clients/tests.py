from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.offers.models import Offer
from apps.surveys.models import Survey
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestAdminClientEndpoints:
    def test_admin_can_create_update_list_delete_client(self, mock_firebase):
        admin = User.objects.create(id="admin-client-1", email="admin-client-1@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client_api.post(
            "/api/v1/admin/clients/",
            {"name": "Acme", "client_code": "ACME001", "email": "hello@acme.com"},
            format="json",
        )
        assert create.status_code == 201
        client_id = create.data["id"]

        listing = client_api.get("/api/v1/admin/clients/")
        assert listing.status_code == 200
        assert listing.data["count"] == 1

        update = client_api.patch(
            f"/api/v1/admin/clients/{client_id}/",
            {"name": "Acme Updated"},
            format="json",
        )
        assert update.status_code == 200
        assert update.data["name"] == "Acme Updated"

        delete = client_api.delete(f"/api/v1/admin/clients/{client_id}/")
        assert delete.status_code == 204
        assert not Client.objects.filter(id=client_id).exists()

    def test_client_code_must_be_unique(self, mock_firebase):
        admin = User.objects.create(id="admin-client-2", email="admin-client-2@b.com", is_admin=True)
        Client.objects.create(id="client-existing", name="Existing", client_code="UNIQUE001")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client_api.post(
            "/api/v1/admin/clients/",
            {"name": "New", "client_code": "UNIQUE001"},
            format="json",
        )
        assert resp.status_code == 400

    def test_client_code_is_immutable_on_update(self, mock_firebase):
        admin = User.objects.create(id="admin-client-3", email="admin-client-3@b.com", is_admin=True)
        created = Client.objects.create(id="client-immutable", name="Immutable", client_code="IMM001")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client_api.patch(
            f"/api/v1/admin/clients/{created.id}/",
            {"client_code": "IMM002"},
            format="json",
        )
        assert resp.status_code == 400

    def test_multiple_clients_can_have_blank_client_code(self, mock_firebase):
        admin = User.objects.create(id="admin-client-blank", email="admin-client-blank@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")

        first = client_api.post("/api/v1/admin/clients/", {"name": "Blank 1"}, format="json")
        second = client_api.post("/api/v1/admin/clients/", {"name": "Blank 2"}, format="json")
        assert first.status_code == 201
        assert second.status_code == 201

    def test_logo_upload(self, mock_firebase):
        admin = User.objects.create(id="admin-client-4", email="admin-client-4@b.com", is_admin=True)
        created = Client.objects.create(id="client-logo-1", name="Logo")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.clients.views.upload_file") as mock_upload:
            mock_upload.return_value = "https://cdn.example/clients/client-logo-1/logo"
            file_obj = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
            resp = client_api.post(
                f"/api/v1/admin/clients/{created.id}/upload-logo/",
                {"file": file_obj},
                format="multipart",
            )

        assert resp.status_code == 200
        created.refresh_from_db()
        assert created.logo_url == "https://cdn.example/clients/client-logo-1/logo"

    def test_logo_upload_rejects_spoofed_content_type(self, mock_firebase):
        admin = User.objects.create(id="admin-client-6", email="admin-client-6@b.com", is_admin=True)
        created = Client.objects.create(id="client-logo-spoof", name="Logo Spoof")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")
        file_obj = SimpleUploadedFile("logo.png", b"not-a-real-image", content_type="image/png")
        resp = client_api.post(
            f"/api/v1/admin/clients/{created.id}/upload-logo/",
            {"file": file_obj},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_delete_returns_409_when_referenced_by_survey_or_offer(self, mock_firebase):
        admin = User.objects.create(id="admin-client-5", email="admin-client-5@b.com", is_admin=True)
        created = Client.objects.create(id="client-ref-1", name="Referenced")
        Survey.objects.create(id="survey-ref-1", title="Survey Ref", client_id=created.id, status="draft")
        Offer.objects.create(id="offer-ref-1", title="Offer Ref", client_id=created.id, status="active")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client_api = APIClient()
        client_api.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client_api.delete(f"/api/v1/admin/clients/{created.id}/")
        assert resp.status_code == 409
