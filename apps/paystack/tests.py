from unittest.mock import patch

import pytest
import requests
from django.conf import settings
from rest_framework.test import APIClient

from apps.users.models import User
import services.paystack as paystack_service


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


def _authed_client(mock_firebase):
    mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
    User.objects.create(id="u1", email="a@b.com")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token")
    return client


@pytest.mark.django_db
class TestPaystackProxyEndpoints:
    def test_banks_returns_200(self, mock_firebase):
        client = _authed_client(mock_firebase)
        with patch("apps.paystack.views.paystack_service.list_banks") as list_banks:
            list_banks.return_value = {"status": True, "data": [{"name": "MTN"}]}
            resp = client.get("/api/v1/paystack/banks/?type=mobile_money&currency=GHS")
        assert resp.status_code == 200
        list_banks.assert_called_once_with(type="mobile_money", currency="GHS")

    def test_banks_http_error_returns_502(self, mock_firebase):
        client = _authed_client(mock_firebase)
        with patch("apps.paystack.views.paystack_service.list_banks") as list_banks:
            list_banks.side_effect = requests.HTTPError("upstream failed")
            resp = client.get("/api/v1/paystack/banks/")
        assert resp.status_code == 502

    def test_transfer_recipient_returns_201(self, mock_firebase):
        client = _authed_client(mock_firebase)
        payload = {
            "name": "Cedric Bansah",
            "account_number": "0240000000",
            "bank_code": "MTN",
        }
        with patch(
            "apps.paystack.views.paystack_service.create_transfer_recipient"
        ) as create_recipient:
            create_recipient.return_value = {"status": True, "data": {"recipient_code": "RCP_1"}}
            resp = client.post("/api/v1/paystack/transfer-recipients/", payload, format="json")
        assert resp.status_code == 201
        create_recipient.assert_called_once_with(
            name="Cedric Bansah",
            account_number="0240000000",
            bank_code="MTN",
            type="mobile_money",
            currency="GHS",
        )

    def test_transfer_recipient_validation_returns_400(self, mock_firebase):
        client = _authed_client(mock_firebase)
        resp = client.post(
            "/api/v1/paystack/transfer-recipients/",
            {"name": "Cedric"},
            format="json",
        )
        assert resp.status_code == 400

    def test_transfers_returns_201(self, mock_firebase):
        client = _authed_client(mock_firebase)
        payload = {
            "recipient": "RCP_1",
            "amount": 1000,
            "reference": "REF_1",
        }
        with patch("apps.paystack.views.paystack_service.initiate_transfer") as initiate_transfer:
            initiate_transfer.return_value = {"status": True, "data": {"transfer_code": "TRF_1"}}
            resp = client.post("/api/v1/paystack/transfers/", payload, format="json")
        assert resp.status_code == 201
        initiate_transfer.assert_called_once_with(
            recipient="RCP_1",
            amount_kobo=1000,
            reference="REF_1",
            reason="LookSharp cashout",
        )

    def test_transfers_validation_returns_400(self, mock_firebase):
        client = _authed_client(mock_firebase)
        resp = client.post(
            "/api/v1/paystack/transfers/",
            {"recipient": "RCP_1", "amount": 0},
            format="json",
        )
        assert resp.status_code == 400

    def test_finalize_returns_200(self, mock_firebase):
        client = _authed_client(mock_firebase)
        with patch("apps.paystack.views.paystack_service.finalize_transfer") as finalize_transfer:
            finalize_transfer.return_value = {"status": True}
            resp = client.post("/api/v1/paystack/transfers/TRF_1/finalize/", {}, format="json")
        assert resp.status_code == 200
        finalize_transfer.assert_called_once_with("TRF_1")

    def test_finalize_http_error_returns_502(self, mock_firebase):
        client = _authed_client(mock_firebase)
        with patch("apps.paystack.views.paystack_service.finalize_transfer") as finalize_transfer:
            finalize_transfer.side_effect = requests.HTTPError("upstream failed")
            resp = client.post("/api/v1/paystack/transfers/TRF_1/finalize/", {}, format="json")
        assert resp.status_code == 502

    def test_unauthenticated_request_returns_401(self):
        client = APIClient()
        resp = client.get("/api/v1/paystack/banks/")
        assert resp.status_code == 401


class TestPaystackService:
    def test_list_banks_calls_request_with_query_params(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status": true, "data": []}'

        with patch("services.paystack.requests.request", return_value=response) as request_call:
            result = paystack_service.list_banks(type="mobile_money", currency="GHS")

        assert result == {"status": True, "data": []}
        request_call.assert_called_once_with(
            "GET",
            "https://api.paystack.co/bank",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
            params={"type": "mobile_money", "currency": "GHS"},
        )

    def test_create_transfer_recipient_posts_expected_payload(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status": true, "data": {"recipient_code": "RCP_1"}}'

        with patch("services.paystack.requests.request", return_value=response) as request_call:
            result = paystack_service.create_transfer_recipient(
                name="Cedric Bansah",
                account_number="0240000000",
                bank_code="MTN",
            )

        assert result["data"]["recipient_code"] == "RCP_1"
        request_call.assert_called_once_with(
            "POST",
            "https://api.paystack.co/transferrecipient",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
            json={
                "type": "mobile_money",
                "name": "Cedric Bansah",
                "account_number": "0240000000",
                "bank_code": "MTN",
                "currency": "GHS",
            },
        )

    def test_initiate_transfer_posts_expected_payload(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status": true, "data": {"transfer_code": "TRF_1"}}'

        with patch("services.paystack.requests.request", return_value=response) as request_call:
            result = paystack_service.initiate_transfer(
                recipient="RCP_1",
                amount_kobo=1000,
                reference="REF_1",
            )

        assert result["data"]["transfer_code"] == "TRF_1"
        request_call.assert_called_once_with(
            "POST",
            "https://api.paystack.co/transfer",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
            json={
                "source": "balance",
                "recipient": "RCP_1",
                "amount": 1000,
                "reference": "REF_1",
                "reason": "LookSharp cashout",
            },
        )

    def test_finalize_transfer_posts_expected_payload(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status": true}'

        with patch("services.paystack.requests.request", return_value=response) as request_call:
            result = paystack_service.finalize_transfer("TRF_1")

        assert result == {"status": True}
        request_call.assert_called_once_with(
            "POST",
            "https://api.paystack.co/transfer/finalize_transfer",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
            json={"transfer_code": "TRF_1"},
        )

    def test_request_raises_for_http_errors(self):
        response = requests.Response()
        response.status_code = 400
        response._content = b'{"message": "bad request"}'

        with patch("services.paystack.requests.request", return_value=response):
            with pytest.raises(requests.HTTPError):
                paystack_service.list_banks()
