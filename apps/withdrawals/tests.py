from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from apps.withdrawals.models import Withdrawal


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestWithdrawalEndpoint:
    def test_verified_user_can_create_withdrawal(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(
            id="u1",
            email="a@b.com",
            is_verified=True,
            points=500,
            recipient_code="RCP_USER_1",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "transfer_reference": "REF_unique_1",
            },
            format="json",
        )
        assert resp.status_code == 201
        created = Withdrawal.objects.get(user_id="u1")
        assert created.recipient_code == "RCP_USER_1"

    def test_unverified_user_gets_403(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com", is_verified=False)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "transfer_reference": "REF_2",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_below_minimum_amount_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@c.com"}
        User.objects.create(
            id="u3",
            email="c@c.com",
            is_verified=True,
            recipient_code="RCP_USER_3",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "2.00",
                "points_converted": 20,
                "transfer_reference": "REF_3",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_points_above_user_balance_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u4", "email": "d@d.com"}
        User.objects.create(
            id="u4",
            email="d@d.com",
            is_verified=True,
            points=50,
            recipient_code="RCP_USER_4",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "transfer_reference": "REF_4",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_user_with_active_withdrawal_gets_409(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u5", "email": "e@e.com"}
        User.objects.create(
            id="u5",
            email="e@e.com",
            is_verified=True,
            points=500,
            recipient_code="RCP_USER_5",
        )
        Withdrawal.objects.create(
            user_id="u5",
            amount_ghs="10.00",
            points_converted=100,
            recipient_code="RCP_USER_5",
            transfer_reference="REF_existing",
            status="pending",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "transfer_reference": "REF_new",
            },
            format="json",
        )
        assert resp.status_code == 409

    def test_user_without_recipient_code_gets_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u6", "email": "f@f.com"}
        User.objects.create(id="u6", email="f@f.com", is_verified=True, points=500, recipient_code="")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "transfer_reference": "REF_6",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_client_cannot_spoof_recipient_code(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u7", "email": "g@g.com"}
        User.objects.create(
            id="u7",
            email="g@g.com",
            is_verified=True,
            points=500,
            recipient_code="RCP_USER_7",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "recipient_code": "RCP_ATTACKER",
                "transfer_reference": "REF_7",
            },
            format="json",
        )
        assert resp.status_code == 201
        created = Withdrawal.objects.get(user_id="u7")
        assert created.recipient_code == "RCP_USER_7"
