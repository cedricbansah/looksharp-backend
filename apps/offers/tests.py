from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.offers.models import Offer, Redemption
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestOfferEndpoints:
    def test_list_returns_active_offers(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Offer.objects.create(id="o1", title="A", status="active", is_deleted=False)
        Offer.objects.create(id="o2", title="B", status="inactive", is_deleted=False)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/offers/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["id"] == "o1"

    def test_redeem_offer_deducts_points(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com", points=200)
        Offer.objects.create(
            id="o1",
            title="Offer",
            status="active",
            points_required=100,
            client_name="Client",
            offer_code="CODE1",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")

        assert resp.status_code == 201
        assert Redemption.objects.filter(user_id="u2", offer_id="o1").count() == 1
        assert User.objects.get(id="u2").points == 100

    def test_redeem_offer_is_idempotent(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@b.com"}
        User.objects.create(id="u3", email="c@b.com", points=200)
        Offer.objects.create(
            id="o2",
            title="Offer",
            status="active",
            points_required=100,
            client_name="Client",
            offer_code="CODE2",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        first = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")
        second = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")

        assert first.status_code == 201
        assert second.status_code == 200
        assert Redemption.objects.filter(user_id="u3", offer_id="o2").count() == 1
        assert User.objects.get(id="u3").points == 100

    def test_redeem_offer_insufficient_points_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u4", "email": "d@b.com"}
        User.objects.create(id="u4", email="d@b.com", points=10)
        Offer.objects.create(id="o3", title="Offer", status="active", points_required=100)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o3"}, format="json")

        assert resp.status_code == 400

    def test_redeem_requires_auth(self):
        client = APIClient()
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestAdminOfferEndpoints:
    def test_admin_create_update_delete_offer(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-1", email="admin-offer-1@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client.post(
            "/api/v1/admin/offers/",
            {"title": "Offer A", "status": "inactive", "points_required": 20},
            format="json",
        )
        assert create.status_code == 201
        offer_id = create.data["id"]

        update = client.patch(
            f"/api/v1/admin/offers/{offer_id}/",
            {"status": "active", "title": "Offer A+"},
            format="json",
        )
        assert update.status_code == 200
        assert update.data["status"] == "active"
        assert update.data["title"] == "Offer A+"

        delete = client.delete(f"/api/v1/admin/offers/{offer_id}/")
        assert delete.status_code == 204
        assert not Offer.objects.filter(id=offer_id).exists()

    def test_admin_delete_offer_with_redemptions_returns_409(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-2", email="admin-offer-2@b.com", is_admin=True)
        user = User.objects.create(id="member-offer-2", email="member-offer-2@b.com")
        offer = Offer.objects.create(id="offer-guard-1", title="Guard Offer", status="active", points_required=10)
        Redemption.objects.create(
            user_id=user.id,
            offer=offer,
            offer_code="C1",
            offer_title=offer.title,
            client_name="Client",
            points_spent=10,
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.delete(f"/api/v1/admin/offers/{offer.id}/")
        assert resp.status_code == 409

    def test_admin_poster_upload_rejects_invalid_type(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-3", email="admin-offer-3@b.com", is_admin=True)
        offer = Offer.objects.create(id="offer-upload-1", title="Upload Offer", status="active")

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        file_obj = SimpleUploadedFile("poster.txt", b"not-an-image", content_type="text/plain")
        resp = client.post(
            f"/api/v1/admin/offers/{offer.id}/upload-poster/",
            {"file": file_obj},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_admin_poster_upload_updates_offer_url(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-4", email="admin-offer-4@b.com", is_admin=True)
        offer = Offer.objects.create(id="offer-upload-2", title="Upload Offer 2", status="active")

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.offers.views.upload_file") as mock_upload:
            mock_upload.return_value = "https://cdn.example/offers/offer-upload-2/poster"
            file_obj = SimpleUploadedFile("poster.png", b"\x89PNG\r\n", content_type="image/png")
            resp = client.post(
                f"/api/v1/admin/offers/{offer.id}/upload-poster/",
                {"file": file_obj},
                format="multipart",
            )

        assert resp.status_code == 200
        offer.refresh_from_db()
        assert offer.poster_url == "https://cdn.example/offers/offer-upload-2/poster"
