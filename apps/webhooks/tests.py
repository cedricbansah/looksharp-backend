import hashlib
import hmac
import json

import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from apps.withdrawals.models import Withdrawal

TEST_SECRET = "test_secret"


def sign(payload_bytes, secret=TEST_SECRET):
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha512).hexdigest()


def post_webhook(payload_dict, secret=TEST_SECRET):
    client = APIClient()
    raw = json.dumps(payload_dict).encode()
    return client.post(
        "/api/v1/webhooks/paystack/",
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sign(raw, secret),
    )


@pytest.mark.django_db
class TestPaystackWebhook:
    def setup_method(self):
        from django.conf import settings

        settings.PAYSTACK_SECRET_KEY = TEST_SECRET

    def _make_withdrawal(self, **kwargs):
        defaults = dict(
            user_id="u1",
            amount_ghs="10.00",
            points_converted=100,
            recipient_code="RCP_1",
            transfer_reference="REF_1",
            status="pending",
        )
        defaults.update(kwargs)
        return Withdrawal.objects.create(**defaults)

    def test_valid_approval_sets_processing(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal()
        resp = post_webhook({"transfer_code": "TRF_1", "reference": "REF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "processing"

    def test_invalid_signature_returns_401(self):
        client = APIClient()
        raw = json.dumps({"reference": "REF_1"}).encode()
        resp = client.post(
            "/api/v1/webhooks/paystack/",
            data=raw,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="bad",
        )
        assert resp.status_code == 401

    def test_empty_body_returns_400(self):
        client = APIClient()
        resp = client.post("/api/v1/webhooks/paystack/", content_type="application/json")
        assert resp.status_code == 400

    def test_unverified_user_sets_failed(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=False, points=500)
        wd = self._make_withdrawal()
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "User not verified"

    def test_insufficient_points_sets_failed(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=10)
        wd = self._make_withdrawal(points_converted=500)
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        wd.refresh_from_db()
        assert wd.status == "failed"

    def test_completed_withdrawal_sets_failed(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="completed")
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        wd.refresh_from_db()
        assert wd.status == "failed"
