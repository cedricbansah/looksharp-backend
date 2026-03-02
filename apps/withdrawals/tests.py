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
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "10.00",
                "points_converted": 100,
                "recipient_code": "RCP_1",
                "transfer_reference": "REF_unique_1",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert Withdrawal.objects.filter(user_id="u1").count() == 1

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
                "recipient_code": "RCP_1",
                "transfer_reference": "REF_2",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_below_minimum_amount_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@c.com"}
        User.objects.create(id="u3", email="c@c.com", is_verified=True)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post(
            "/api/v1/withdrawals/",
            {
                "amount_ghs": "2.00",
                "points_converted": 20,
                "recipient_code": "RCP_1",
                "transfer_reference": "REF_3",
            },
            format="json",
        )
        assert resp.status_code == 400
