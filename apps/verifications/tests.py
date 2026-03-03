from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from apps.verifications.models import Verification


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestVerificationEndpoints:
    def test_user_can_submit_and_list_own_verifications(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")

        payload = {
            "full_name": "Test User",
            "gender": "male",
            "nationality": "Ghanaian",
            "mobile_number": "0240000000",
            "network_provider": "MTN",
            "id_type": "ghana_card",
            "id_number": "GHA-123",
            "id_front_url": "https://example.com/front.jpg",
            "id_back_url": "https://example.com/back.jpg",
            "selfie_url": "https://example.com/selfie.jpg",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        create_resp = client.post("/api/v1/verifications/", payload, format="json")
        list_resp = client.get("/api/v1/verifications/")

        assert create_resp.status_code == 201
        assert create_resp.data["status"] == "pending"
        assert list_resp.status_code == 200
        assert len(list_resp.data["results"]) == 1

    def test_admin_can_approve_verification(self, mock_firebase):
        admin = User.objects.create(id="admin", email="admin@b.com", is_admin=True)
        target = User.objects.create(id="u2", email="u2@b.com", is_verified=False)
        verification = Verification.objects.create(
            user_id=target.id,
            full_name="Target User",
            mobile_number="0240000001",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-222",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="pending",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(f"/api/v1/admin/verifications/{verification.id}/approve/", {}, format="json")

        assert resp.status_code == 200
        verification.refresh_from_db()
        target.refresh_from_db()
        assert verification.status == "approved"
        assert target.is_verified is True

    def test_admin_can_reject_verification(self, mock_firebase):
        admin = User.objects.create(id="admin2", email="admin2@b.com", is_admin=True)
        target = User.objects.create(id="u3", email="u3@b.com")
        verification = Verification.objects.create(
            user_id=target.id,
            full_name="Target User",
            mobile_number="0240000002",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-333",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="pending",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            f"/api/v1/admin/verifications/{verification.id}/reject/",
            {"rejection_reason": "Invalid details"},
            format="json",
        )

        assert resp.status_code == 200
        verification.refresh_from_db()
        assert verification.status == "rejected"
        assert verification.rejection_reason == "Invalid details"

    def test_admin_can_create_recipient(self, mock_firebase):
        admin = User.objects.create(id="admin3", email="admin3@b.com", is_admin=True)
        target = User.objects.create(id="u4", email="u4@b.com")
        verification = Verification.objects.create(
            user_id=target.id,
            full_name="Target User",
            mobile_number="0240000003",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-444",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="approved",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.verifications.views.paystack_service.create_transfer_recipient") as create_recipient:
            create_recipient.return_value = {"status": True, "data": {"recipient_code": "RCP_123"}}
            resp = client.post(
                f"/api/v1/admin/verifications/{verification.id}/create-recipient/",
                {},
                format="json",
            )

        assert resp.status_code == 201
        target.refresh_from_db()
        assert target.recipient_code == "RCP_123"

    def test_non_admin_cannot_access_admin_endpoints(self, mock_firebase):
        user = User.objects.create(id="u5", email="u5@b.com", is_admin=False)
        verification = Verification.objects.create(
            user_id=user.id,
            full_name="Target User",
            mobile_number="0240000005",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-555",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="pending",
        )

        mock_firebase.return_value = {"uid": user.id, "email": user.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/admin/verifications/")

        assert resp.status_code == 403

        approve_resp = client.post(
            f"/api/v1/admin/verifications/{verification.id}/approve/",
            {},
            format="json",
        )
        assert approve_resp.status_code == 403
