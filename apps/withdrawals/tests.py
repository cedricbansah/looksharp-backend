from unittest.mock import patch

import pytest
import requests as http_requests
from celery.exceptions import Retry
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import User
from apps.withdrawals.models import Withdrawal
from apps.withdrawals.tasks import initiate_withdrawal_transfer


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
        with patch("apps.withdrawals.views.transaction.on_commit", side_effect=lambda fn: fn()), patch(
            "apps.withdrawals.views.initiate_withdrawal_transfer.delay"
        ) as queue_task:
            resp = client.post(
                "/api/v1/withdrawals/",
                {
                    "amount_ghs": "10.00",
                    "points_converted": 100,
                },
                format="json",
            )
        assert resp.status_code == 201
        created = Withdrawal.objects.get(user_id="u1")
        assert created.recipient_code == "RCP_USER_1"
        assert created.transfer_reference.startswith("wd_")
        queue_task.assert_called_once_with(str(created.id))

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
                "transfer_reference": "ATTACKER_REFERENCE",
            },
            format="json",
        )
        assert resp.status_code == 201
        created = Withdrawal.objects.get(user_id="u7")
        assert created.recipient_code == "RCP_USER_7"
        assert created.transfer_reference != "ATTACKER_REFERENCE"


@pytest.mark.django_db
class TestAdminWithdrawalUpdateEndpoint:
    def test_admin_can_mark_completed_and_deduct_points(self, mock_firebase):
        admin = User.objects.create(id="admin-wd-1", email="admin-wd-1@b.com", is_admin=True)
        user = User.objects.create(id="user-wd-1", email="user-wd-1@b.com", points=300)
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="20.00",
            points_converted=100,
            recipient_code="RCP_1",
            transfer_reference="REF_admin_completed",
            status="processing",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.patch(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/",
            {"status": "completed"},
            format="json",
        )
        assert resp.status_code == 200
        withdrawal.refresh_from_db()
        user.refresh_from_db()
        assert withdrawal.status == "completed"
        assert withdrawal.completed_at is not None
        assert user.points == 200

    def test_admin_can_mark_failed_without_changing_points(self, mock_firebase):
        admin = User.objects.create(id="admin-wd-2", email="admin-wd-2@b.com", is_admin=True)
        user = User.objects.create(id="user-wd-2", email="user-wd-2@b.com", points=50)
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=25,
            recipient_code="RCP_2",
            transfer_reference="REF_admin_failed",
            status="processing",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.patch(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/",
            {"status": "failed", "failure_reason": "Bank rejected transfer"},
            format="json",
        )
        assert resp.status_code == 200
        withdrawal.refresh_from_db()
        user.refresh_from_db()
        assert withdrawal.status == "failed"
        assert withdrawal.failure_reason == "Bank rejected transfer"
        assert user.points == 50

    def test_admin_completed_rejects_when_user_points_insufficient(self, mock_firebase):
        admin = User.objects.create(id="admin-wd-5", email="admin-wd-5@b.com", is_admin=True)
        user = User.objects.create(id="user-wd-5", email="user-wd-5@b.com", points=10)
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=25,
            recipient_code="RCP_5",
            transfer_reference="REF_admin_insufficient",
            status="processing",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.patch(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/",
            {"status": "completed"},
            format="json",
        )
        assert resp.status_code == 400
        withdrawal.refresh_from_db()
        user.refresh_from_db()
        assert withdrawal.status == "processing"
        assert user.points == 10

    def test_admin_failed_status_requires_failure_reason(self, mock_firebase):
        admin = User.objects.create(id="admin-wd-3", email="admin-wd-3@b.com", is_admin=True)
        user = User.objects.create(id="user-wd-3", email="user-wd-3@b.com", points=50)
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=25,
            recipient_code="RCP_3",
            transfer_reference="REF_admin_failed_validate",
            status="pending",
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.patch(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/",
            {"status": "failed"},
            format="json",
        )
        assert resp.status_code == 400

    def test_admin_cannot_change_terminal_withdrawal(self, mock_firebase):
        admin = User.objects.create(id="admin-wd-4", email="admin-wd-4@b.com", is_admin=True)
        user = User.objects.create(id="user-wd-4", email="user-wd-4@b.com", points=500)
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=25,
            recipient_code="RCP_4",
            transfer_reference="REF_admin_terminal",
            status="completed",
            completed_at=timezone.now(),
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.patch(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/",
            {"status": "failed", "failure_reason": "late change"},
            format="json",
        )
        assert resp.status_code == 409


@pytest.mark.django_db
class TestInitiateWithdrawalTransferTask:
    def test_moves_pending_withdrawal_to_processing(self):
        user = User.objects.create(
            id="task-user-1",
            email="task-user-1@example.com",
            points=500,
            recipient_code="RCP_123",
        )
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=100,
            recipient_code=user.recipient_code,
            transfer_reference="wd_task_success",
            status="pending",
        )

        with patch("apps.withdrawals.tasks.paystack_service.initiate_transfer") as initiate_transfer:
            initiate_transfer.return_value = {"status": True, "data": {"transfer_code": "TRF_123"}}
            result = initiate_withdrawal_transfer.run(str(withdrawal.id))

        withdrawal.refresh_from_db()
        assert result["success"] is True
        assert withdrawal.status == "processing"
        assert withdrawal.transfer_code == "TRF_123"
        assert withdrawal.failure_reason == ""

    def test_skips_non_pending_withdrawal(self):
        user = User.objects.create(
            id="task-user-2",
            email="task-user-2@example.com",
            points=500,
            recipient_code="RCP_456",
        )
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=100,
            recipient_code=user.recipient_code,
            transfer_reference="wd_task_skip",
            status="processing",
            transfer_code="TRF_EXISTING",
        )

        with patch("apps.withdrawals.tasks.paystack_service.initiate_transfer") as initiate_transfer:
            result = initiate_withdrawal_transfer.run(str(withdrawal.id))

        assert result["detail"] == "already processed"
        initiate_transfer.assert_not_called()

    def test_marks_withdrawal_failed_when_points_are_insufficient(self):
        user = User.objects.create(
            id="task-user-3",
            email="task-user-3@example.com",
            points=50,
            recipient_code="RCP_789",
        )
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=100,
            recipient_code=user.recipient_code,
            transfer_reference="wd_task_insufficient",
            status="pending",
        )

        result = initiate_withdrawal_transfer.run(str(withdrawal.id))

        withdrawal.refresh_from_db()
        assert result["success"] is False
        assert withdrawal.status == "failed"
        assert withdrawal.failure_reason == "Insufficient points for this withdrawal."

    def test_retries_on_transport_errors(self):
        user = User.objects.create(
            id="task-user-4",
            email="task-user-4@example.com",
            points=500,
            recipient_code="RCP_321",
        )
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=100,
            recipient_code=user.recipient_code,
            transfer_reference="wd_task_retry",
            status="pending",
        )

        with patch("apps.withdrawals.tasks.paystack_service.initiate_transfer") as initiate_transfer, patch.object(
            initiate_withdrawal_transfer,
            "retry",
            side_effect=Retry(),
        ) as retry_call:
            initiate_transfer.side_effect = http_requests.ConnectionError("network down")
            with pytest.raises(Retry):
                initiate_withdrawal_transfer.run(str(withdrawal.id))

        withdrawal.refresh_from_db()
        assert withdrawal.status == "pending"
        retry_call.assert_called_once()

    def test_marks_withdrawal_failed_on_terminal_http_error(self):
        user = User.objects.create(
            id="task-user-5",
            email="task-user-5@example.com",
            points=500,
            recipient_code="RCP_654",
        )
        withdrawal = Withdrawal.objects.create(
            user_id=user.id,
            amount_ghs="10.00",
            points_converted=100,
            recipient_code=user.recipient_code,
            transfer_reference="wd_task_http_error",
            status="pending",
        )
        response = http_requests.Response()
        response.status_code = 400
        response._content = b'{"message":"Balance too low"}'

        with patch("apps.withdrawals.tasks.paystack_service.initiate_transfer") as initiate_transfer:
            initiate_transfer.side_effect = http_requests.HTTPError("bad request", response=response)
            result = initiate_withdrawal_transfer.run(str(withdrawal.id))

        withdrawal.refresh_from_db()
        assert result["success"] is False
        assert withdrawal.status == "failed"
        assert withdrawal.failure_reason == "Balance too low"
