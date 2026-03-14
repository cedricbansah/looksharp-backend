from unittest.mock import patch

import pytest
import requests as http_requests
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
        target = User.objects.create(id="u2", email="u2@b.com", is_verified=False, recipient_code="RCP_321")
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
        with patch("apps.verifications.tasks.notify_user_kyc_decision.delay") as queue_sms:
            resp = client.post(f"/api/v1/admin/verifications/{verification.id}/approve/", {}, format="json")

        assert resp.status_code == 200
        verification.refresh_from_db()
        target.refresh_from_db()
        assert verification.status == "approved"
        assert target.is_verified is True
        queue_sms.assert_called_once_with(verification.id)

    def test_admin_cannot_approve_without_recipient_code(self, mock_firebase):
        admin = User.objects.create(id="admin-no-recipient", email="admin-no-recipient@b.com", is_admin=True)
        target = User.objects.create(id="u2-no-recipient", email="u2-no-recipient@b.com", is_verified=False)
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

        assert resp.status_code == 400
        assert resp.data["error"] == "Generate recipient code before approving this verification."
        verification.refresh_from_db()
        target.refresh_from_db()
        assert verification.status == "pending"
        assert target.is_verified is False

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
        with patch("apps.verifications.tasks.notify_user_kyc_decision.delay") as queue_sms:
            resp = client.post(
                f"/api/v1/admin/verifications/{verification.id}/reject/",
                {"rejection_reason": "Invalid details"},
                format="json",
            )

        assert resp.status_code == 200
        verification.refresh_from_db()
        assert verification.status == "rejected"
        assert verification.rejection_reason == "Invalid details"
        queue_sms.assert_called_once_with(verification.id)

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

    def test_create_recipient_returns_existing_code_without_calling_paystack(self, mock_firebase):
        admin = User.objects.create(id="admin3-existing", email="admin3-existing@b.com", is_admin=True)
        target = User.objects.create(id="u4-existing", email="u4-existing@b.com", recipient_code="RCP_EXISTING")
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
            status="pending",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.verifications.views.paystack_service.create_transfer_recipient") as create_recipient:
            resp = client.post(
                f"/api/v1/admin/verifications/{verification.id}/create-recipient/",
                {},
                format="json",
            )

        assert resp.status_code == 200
        assert resp.data["recipient_code"] == "RCP_EXISTING"
        create_recipient.assert_not_called()

    def test_create_recipient_returns_409_for_rejected_verification(self, mock_firebase):
        admin = User.objects.create(id="admin-rejected-recipient", email="admin-rejected-recipient@b.com", is_admin=True)
        target = User.objects.create(id="u4-rejected", email="u4-rejected@b.com")
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
            status="rejected",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            f"/api/v1/admin/verifications/{verification.id}/create-recipient/",
            {},
            format="json",
        )

        assert resp.status_code == 409
        assert resp.data["error"] == "Verification is not actionable in status rejected."

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

    def test_admin_can_list_all_verifications(self, mock_firebase):
        admin = User.objects.create(id="admin-list", email="admin-list@b.com", is_admin=True)
        Verification.objects.create(
            user_id="u10",
            full_name="User One",
            mobile_number="0240000010",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-1010",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="pending",
        )
        Verification.objects.create(
            user_id="u11",
            full_name="User Two",
            mobile_number="0240000011",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-1111",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="approved",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.get("/api/v1/admin/verifications/")

        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_approve_returns_404_for_missing_verification(self, mock_firebase):
        admin = User.objects.create(id="admin-miss-approve", email="admin-miss-approve@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.post(
            "/api/v1/admin/verifications/00000000-0000-0000-0000-000000000000/approve/",
            {},
            format="json",
        )

        assert response.status_code == 404

    def test_reject_returns_404_for_missing_verification(self, mock_firebase):
        admin = User.objects.create(id="admin-miss-reject", email="admin-miss-reject@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.post(
            "/api/v1/admin/verifications/00000000-0000-0000-0000-000000000000/reject/",
            {"rejection_reason": "Not found"},
            format="json",
        )

        assert response.status_code == 404

    def test_create_recipient_returns_404_for_missing_verification(self, mock_firebase):
        admin = User.objects.create(id="admin-miss-recipient", email="admin-miss-recipient@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.post(
            "/api/v1/admin/verifications/00000000-0000-0000-0000-000000000000/create-recipient/",
            {},
            format="json",
        )

        assert response.status_code == 404

    def test_create_recipient_returns_502_on_paystack_http_error(self, mock_firebase):
        admin = User.objects.create(id="admin-http-err", email="admin-http-err@b.com", is_admin=True)
        User.objects.create(id="u12", email="u12@example.com")
        verification = Verification.objects.create(
            user_id="u12",
            full_name="Target User",
            mobile_number="0240000012",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-1212",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="approved",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.verifications.views.paystack_service.create_transfer_recipient") as create_recipient:
            response = http_requests.Response()
            response.status_code = 400
            response._content = b'{"message":"Invalid mobile number"}'
            create_recipient.side_effect = http_requests.HTTPError("paystack error", response=response)
            response = client.post(
                f"/api/v1/admin/verifications/{verification.id}/create-recipient/",
                {},
                format="json",
            )

        assert response.status_code == 502
        assert response.data["error"] == "Invalid mobile number"

    def test_create_recipient_returns_502_when_recipient_code_missing(self, mock_firebase):
        admin = User.objects.create(id="admin-missing-code", email="admin-missing-code@b.com", is_admin=True)
        User.objects.create(id="u13", email="u13@example.com")
        verification = Verification.objects.create(
            user_id="u13",
            full_name="Target User",
            mobile_number="0240000013",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-1313",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="approved",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.verifications.views.paystack_service.create_transfer_recipient") as create_recipient:
            create_recipient.return_value = {"status": True, "data": {}}
            response = client.post(
                f"/api/v1/admin/verifications/{verification.id}/create-recipient/",
                {},
                format="json",
            )

        assert response.status_code == 502
