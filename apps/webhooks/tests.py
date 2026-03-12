import hashlib
import hmac
import json
from unittest.mock import patch

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


def post_raw_webhook(raw_payload, secret=TEST_SECRET):
    client = APIClient()
    return client.post(
        "/api/v1/webhooks/paystack/",
        data=raw_payload,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sign(raw_payload, secret),
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
        assert wd.transfer_code == "TRF_1"

    def test_transfer_success_sets_completed_and_deducts_points(self):
        user = User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook(
            {
                "event": "transfer.success",
                "data": {"transfer_code": "TRF_1", "reference": "REF_1"},
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        user.refresh_from_db()
        assert wd.status == "completed"
        assert wd.completed_at is not None
        assert user.points == 400

    def test_transfer_success_replay_is_idempotent(self):
        user = User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        payload = {
            "event": "transfer.success",
            "data": {"transfer_code": "TRF_1", "reference": "REF_1"},
        }
        first = post_webhook(payload)
        second = post_webhook(payload)
        assert first.status_code == 200
        assert second.status_code == 200
        wd.refresh_from_db()
        user.refresh_from_db()
        assert wd.status == "completed"
        assert user.points == 400

    def test_transfer_failed_sets_failed(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook(
            {
                "event": "transfer.failed",
                "data": {
                    "transfer_code": "TRF_1",
                    "reference": "REF_1",
                    "failure_reason": "insufficient balance",
                },
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "insufficient balance"

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

    def test_completed_withdrawal_is_not_downgraded(self):
        user = User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="completed")
        resp = post_webhook(
            {
                "event": "transfer.failed",
                "data": {"transfer_code": "TRF_1", "reference": "REF_1"},
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        user.refresh_from_db()
        assert wd.status == "completed"
        assert user.points == 500

    def test_processing_withdrawal_replay_is_idempotent(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook({"transfer_code": "TRF_1", "reference": "REF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "processing"
        assert wd.transfer_code == "TRF_1"

    def test_processing_with_mismatched_transfer_code_returns_400(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook({"transfer_code": "TRF_2", "reference": "REF_1"})
        assert resp.status_code == 400
        wd.refresh_from_db()
        assert wd.status == "processing"
        assert wd.transfer_code == "TRF_1"

    def test_invalid_json_returns_400(self):
        resp = post_raw_webhook(b"{bad")
        assert resp.status_code == 400
        assert resp.data["error"] == "Invalid JSON"

    def test_missing_identifiers_returns_400(self):
        resp = post_webhook({"event": "transfer.success", "data": {}})
        assert resp.status_code == 400
        assert resp.data["error"] == "Missing transfer identifiers"

    def test_non_dict_data_is_handled(self):
        user = User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook({"event": "transfer.success", "data": "string", "transfer_code": "TRF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        user.refresh_from_db()
        assert wd.status == "completed"
        assert user.points == 400

    def test_approval_required_uses_transfers_list(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal()
        resp = post_webhook(
            {
                "event": "transferrequest.approval-required",
                "data": {"transfers": [{"transfer_code": "TRF_1", "reference": "REF_1"}]},
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "processing"
        assert wd.transfer_code == "TRF_1"

    def test_withdrawal_not_found_returns_400(self):
        resp = post_webhook({"reference": "MISSING_REF"})
        assert resp.status_code == 400
        assert resp.data["error"] == "Transfer not found"

    def test_unhandled_event_returns_200(self):
        wd = self._make_withdrawal()
        resp = post_webhook({"event": "charge.success", "reference": "REF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "pending"

    def test_exception_in_transition_returns_400(self):
        with patch("apps.webhooks.views.transaction.atomic", side_effect=RuntimeError("boom")):
            resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        assert resp.data["error"] == "Internal error"

    def test_approve_failed_withdrawal_is_replay(self):
        wd = self._make_withdrawal(status="failed")
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "failed"

    def test_approve_processing_assigns_missing_transfer_code(self):
        wd = self._make_withdrawal(status="processing")
        resp = post_webhook({"transfer_code": "TRF_NEW", "reference": "REF_1"})
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "processing"
        assert wd.transfer_code == "TRF_NEW"

    def test_approve_invalid_status_returns_400(self):
        wd = self._make_withdrawal(status="cancelled")
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        assert resp.data["error"] == "Invalid withdrawal status: cancelled"
        wd.refresh_from_db()
        assert wd.status == "cancelled"

    def test_approve_user_not_found_returns_400(self):
        wd = self._make_withdrawal(user_id="ghost")
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        assert resp.data["error"] == "User not found"
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "User not found"

    def test_approve_multiple_pending_returns_400(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal()
        self._make_withdrawal(transfer_reference="REF_2")
        resp = post_webhook({"reference": "REF_1"})
        assert resp.status_code == 400
        assert resp.data["error"] == "Multiple pending withdrawals"
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "Multiple pending withdrawals"

    def test_complete_failed_withdrawal_is_replay(self):
        wd = self._make_withdrawal(status="failed", transfer_code="TRF_1")
        resp = post_webhook(
            {
                "event": "transfer.success",
                "data": {"transfer_code": "TRF_1", "reference": "REF_1"},
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "failed"

    def test_complete_invalid_status_returns_400(self):
        wd = self._make_withdrawal(status="cancelled")
        resp = post_webhook({"event": "transfer.success", "data": {"reference": "REF_1"}})
        assert resp.status_code == 400
        assert resp.data["error"] == "Invalid withdrawal status: cancelled"
        wd.refresh_from_db()
        assert wd.status == "cancelled"

    def test_complete_transfer_code_mismatch_returns_400(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        wd = self._make_withdrawal(status="processing", transfer_code="TRF_1")
        resp = post_webhook(
            {
                "event": "transfer.success",
                "data": {"transfer_code": "TRF_2", "reference": "REF_1"},
            }
        )
        assert resp.status_code == 400
        assert resp.data["error"] == "Transfer code mismatch for withdrawal"
        wd.refresh_from_db()
        assert wd.status == "processing"
        assert wd.transfer_code == "TRF_1"

    def test_complete_user_not_found_returns_400(self):
        wd = self._make_withdrawal(user_id="ghost")
        resp = post_webhook({"event": "transfer.success", "data": {"reference": "REF_1"}})
        assert resp.status_code == 400
        assert resp.data["error"] == "User not found"
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "User not found"

    def test_complete_user_not_verified_returns_400(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=False, points=500)
        wd = self._make_withdrawal()
        resp = post_webhook({"event": "transfer.success", "data": {"reference": "REF_1"}})
        assert resp.status_code == 400
        assert resp.data["error"] == "User not verified"
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "User not verified"

    def test_complete_insufficient_points_returns_400(self):
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=10)
        wd = self._make_withdrawal(points_converted=500)
        resp = post_webhook({"event": "transfer.success", "data": {"reference": "REF_1"}})
        assert resp.status_code == 400
        assert resp.data["error"] == "Insufficient points"
        wd.refresh_from_db()
        assert wd.status == "failed"
        assert wd.failure_reason == "Insufficient points"

    def test_fail_completed_withdrawal_is_replay(self):
        wd = self._make_withdrawal(status="completed", transfer_code="TRF_1")
        resp = post_webhook(
            {
                "event": "transfer.reversed",
                "data": {"transfer_code": "TRF_1", "reference": "REF_1"},
            }
        )
        assert resp.status_code == 200
        wd.refresh_from_db()
        assert wd.status == "completed"

    def test_fail_invalid_status_returns_400(self):
        wd = self._make_withdrawal(status="cancelled")
        resp = post_webhook({"event": "transfer.failed", "data": {"reference": "REF_1"}})
        assert resp.status_code == 400
        assert resp.data["error"] == "Invalid withdrawal status: cancelled"
        wd.refresh_from_db()
        assert wd.status == "cancelled"
