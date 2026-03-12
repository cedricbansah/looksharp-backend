from unittest.mock import patch
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.offers.models import Offer, Redemption
from apps.offers.tasks import _days_remaining, recompute_status
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
        Offer.objects.create(id="o1", title="A", status="active")
        Offer.objects.create(id="o2", title="B", status="inactive")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/offers/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["id"] == "o1"

    def test_list_excludes_expired_offers(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1b", "email": "ab@b.com"}
        User.objects.create(id="u1b", email="ab@b.com")
        now = timezone.now()
        Offer.objects.create(id="o1b", title="Expired", status="active", end_date=now - timedelta(minutes=1))
        Offer.objects.create(id="o2b", title="Valid", status="active", end_date=now + timedelta(days=1))

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/offers/")

        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == "o2b"

    def test_redeem_offer_does_not_deduct_points(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com", points=200)
        client_obj = Client.objects.create(id="client-offer-1", name="Client")
        Offer.objects.create(
            id="o1",
            title="Offer",
            status="active",
            client=client_obj,
            offer_code="CODE1",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")

        assert resp.status_code == 201
        assert Redemption.objects.filter(user_id="u2", offer_id="o1").count() == 1
        assert User.objects.get(id="u2").points == 200

    def test_redeem_offer_is_idempotent(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@b.com"}
        User.objects.create(id="u3", email="c@b.com", points=200)
        client_obj = Client.objects.create(id="client-offer-2", name="Client")
        Offer.objects.create(
            id="o2",
            title="Offer",
            status="active",
            client=client_obj,
            offer_code="CODE2",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        first = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")
        second = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")

        assert first.status_code == 201
        assert second.status_code == 200
        assert Redemption.objects.filter(user_id="u3", offer_id="o2").count() == 1
        assert User.objects.get(id="u3").points == 200

    def test_redeem_offer_ignores_user_points(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u4", "email": "d@b.com"}
        User.objects.create(id="u4", email="d@b.com", points=10)
        Offer.objects.create(id="o3", title="Offer", status="active")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o3"}, format="json")

        assert resp.status_code == 201
        assert User.objects.get(id="u4").points == 10

    def test_redeem_expired_offer_returns_404(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u4b", "email": "db@b.com"}
        User.objects.create(id="u4b", email="db@b.com", points=10)
        Offer.objects.create(
            id="o4b",
            title="Expired",
            status="active",
            end_date=timezone.now() - timedelta(minutes=1),
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o4b"}, format="json")

        assert resp.status_code == 404

    def test_redeem_requires_auth(self):
        client = APIClient()
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestAdminOfferEndpoints:
    def test_admin_create_offer_inherits_client_code(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-inherit-1", email="admin-offer-inherit-1@b.com", is_admin=True)
        client_obj = Client.objects.create(id="client-offer-inherit-1", name="Acme", client_code="ACME001")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client.post(
            "/api/v1/admin/offers/",
            {
                "title": "Offer Inherit",
                "status": "inactive",
                "client_id": client_obj.id,
            },
            format="json",
        )

        assert create.status_code == 201
        assert create.data["offer_code"] == "ACME001"
        assert Offer.objects.get(id=create.data["id"]).offer_code == "ACME001"

    def test_admin_create_offer_rejects_manual_offer_code(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-manual-1", email="admin-offer-manual-1@b.com", is_admin=True)
        client_obj = Client.objects.create(id="client-offer-manual-1", name="Acme", client_code="ACME001")
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client.post(
            "/api/v1/admin/offers/",
            {
                "title": "Offer Manual",
                "status": "inactive",
                "client_id": client_obj.id,
                "offer_code": "MANUAL001",
            },
            format="json",
        )

        assert create.status_code == 400
        assert "offer_code" in create.data["error"]

    def test_admin_update_offer_rejects_manual_offer_code(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-manual-2", email="admin-offer-manual-2@b.com", is_admin=True)
        client_obj = Client.objects.create(id="client-offer-manual-2", name="Acme", client_code="ACME001")
        offer = Offer.objects.create(
            id="offer-manual-update-1",
            title="Offer Manual Update",
            status="inactive",
            client=client_obj,
            offer_code="ACME001",
        )
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        update = client.patch(
            f"/api/v1/admin/offers/{offer.id}/",
            {"offer_code": "MANUAL002"},
            format="json",
        )

        assert update.status_code == 400
        offer.refresh_from_db()
        assert offer.offer_code == "ACME001"

    def test_admin_update_offer_client_updates_offer_code(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-client-swap", email="admin-offer-client-swap@b.com", is_admin=True)
        first_client = Client.objects.create(id="client-offer-swap-1", name="Acme", client_code="ACME001")
        second_client = Client.objects.create(id="client-offer-swap-2", name="Beta", client_code="BETA001")
        offer = Offer.objects.create(
            id="offer-client-swap-1",
            title="Offer Client Swap",
            status="inactive",
            client=first_client,
            offer_code="ACME001",
        )
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        update = client.patch(
            f"/api/v1/admin/offers/{offer.id}/",
            {"client_id": second_client.id},
            format="json",
        )

        assert update.status_code == 200
        assert update.data["offer_code"] == "BETA001"
        offer.refresh_from_db()
        assert offer.offer_code == "BETA001"

    def test_admin_create_update_delete_offer(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-1", email="admin-offer-1@b.com", is_admin=True)
        client_obj = Client.objects.create(
            id="client-offer-admin-1",
            name="Acme",
            logo_url="https://cdn.example/clients/acme/logo",
        )
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client.post(
            "/api/v1/admin/offers/",
            {
                "title": "Offer A",
                "status": "inactive",
                "client_id": client_obj.id,
            },
            format="json",
        )
        assert create.status_code == 201
        offer_id = create.data["id"]
        assert create.data["client_id"] == client_obj.id
        assert create.data["client_name"] == "Acme"
        assert create.data["client_logo_url"] == "https://cdn.example/clients/acme/logo"

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
        client_obj = Client.objects.create(id="client-offer-guard-1", name="Client")
        offer = Offer.objects.create(
            id="offer-guard-1",
            title="Guard Offer",
            status="active",
            client=client_obj,
        )
        Redemption.objects.create(
            user_id=user.id,
            offer=offer,
            offer_code="C1",
            offer_title=offer.title,
            client_name="Client",
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

    def test_admin_poster_upload_rejects_spoofed_content_type(self, mock_firebase):
        admin = User.objects.create(id="admin-offer-5", email="admin-offer-5@b.com", is_admin=True)
        offer = Offer.objects.create(id="offer-upload-3", title="Upload Offer 3", status="active")

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        file_obj = SimpleUploadedFile("poster.png", b"not-a-real-image", content_type="image/png")
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
            file_obj = SimpleUploadedFile("poster.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
            resp = client.post(
                f"/api/v1/admin/offers/{offer.id}/upload-poster/",
                {"file": file_obj},
                format="multipart",
            )

        assert resp.status_code == 200
        offer.refresh_from_db()
        assert offer.poster_url == "https://cdn.example/offers/offer-upload-2/poster"


@pytest.mark.django_db
class TestRecomputeStatusTask:
    @freeze_time("2026-03-01 12:00:00")
    def test_expires_ended_offers(self):
        now = timezone.now()
        first = Offer.objects.create(
            id="offer-expire-1",
            title="Offer Expire 1",
            status="active",
            end_date=now - timedelta(days=1),
            days_remaining=5,
        )
        second = Offer.objects.create(
            id="offer-expire-2",
            title="Offer Expire 2",
            status="active",
            end_date=now - timedelta(days=2),
            days_remaining=8,
        )

        result = recompute_status.apply().get()

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.status == "inactive"
        assert second.status == "inactive"
        assert first.days_remaining == 0
        assert second.days_remaining == 0
        assert result["ended_count"] == 2

    @freeze_time("2026-03-01 12:00:00")
    def test_updates_stale_days_remaining(self):
        now = timezone.now()
        offer = Offer.objects.create(
            id="offer-days-update-1",
            title="Offer Days Update",
            status="active",
            end_date=now + timedelta(days=5),
            days_remaining=0,
        )

        result = recompute_status.apply().get()

        offer.refresh_from_db()
        assert offer.days_remaining == 5
        assert result["updated_count"] == 1
        assert result["error_count"] == 0

    @freeze_time("2026-03-01 12:00:00")
    def test_skips_offer_with_correct_days_remaining(self):
        now = timezone.now()
        Offer.objects.create(
            id="offer-days-skip-1",
            title="Offer Days Skip",
            status="active",
            end_date=now + timedelta(days=3),
            days_remaining=3,
        )

        result = recompute_status.apply().get()

        assert result["updated_count"] == 0
        assert result["error_count"] == 0
        assert result["ended_count"] == 0

    @freeze_time("2026-03-01 12:00:00")
    def test_handles_per_offer_exception(self):
        now = timezone.now()
        first_end = now + timedelta(days=6)
        second_end = now + timedelta(days=4)
        first = Offer.objects.create(
            id="offer-days-exc-1",
            title="Offer Days Exc 1",
            status="active",
            end_date=first_end,
            days_remaining=0,
        )
        second = Offer.objects.create(
            id="offer-days-exc-2",
            title="Offer Days Exc 2",
            status="active",
            end_date=second_end,
            days_remaining=0,
        )

        def fake_days_remaining(end_date):
            if end_date == first_end:
                raise RuntimeError("boom")
            return 4

        with patch("apps.offers.tasks._days_remaining", side_effect=fake_days_remaining):
            result = recompute_status.apply().get()

        first.refresh_from_db()
        second.refresh_from_db()
        assert result["success"] is True
        assert result["error_count"] == 1
        assert second.days_remaining == 4
        assert first.days_remaining == 0

    def test_days_remaining_none_end_date(self):
        assert _days_remaining(None) == 0
