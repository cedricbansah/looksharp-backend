from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.counters.models import DashboardCounter
from apps.counters.tasks import (
    recompute_active_offers,
    recompute_active_surveys,
    recompute_extended_dashboard,
    recompute_total_paid_out,
    recompute_total_responses,
)
from apps.offers.models import Offer
from apps.responses.models import Response
from apps.surveys.models import Survey
from apps.users.models import User
from apps.verifications.models import Verification
from apps.withdrawals.models import Withdrawal


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestCounterAdminEndpoints:
    def test_admin_dashboard_returns_200(self, mock_firebase):
        admin = User.objects.create(id="admin", email="admin@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.get("/api/v1/admin/dashboard/")
        assert resp.status_code == 200
        assert "active_surveys" in resp.data

    def test_non_admin_dashboard_returns_403(self, mock_firebase):
        user = User.objects.create(id="u1", email="u1@b.com", is_admin=False)
        mock_firebase.return_value = {"uid": user.id, "email": user.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.get("/api/v1/admin/dashboard/")
        assert resp.status_code == 403

    def test_rebuild_dispatches_tasks(self, mock_firebase):
        admin = User.objects.create(id="admin2", email="admin2@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        with patch("apps.counters.views.recompute_active_surveys.delay") as a, patch(
            "apps.counters.views.recompute_active_offers.delay"
        ) as b, patch("apps.counters.views.recompute_total_responses.delay") as c, patch(
            "apps.counters.views.recompute_total_paid_out.delay"
        ) as d, patch("apps.counters.views.recompute_extended_dashboard.delay") as e:
            resp = client.post("/api/v1/admin/counters/rebuild/", {}, format="json")

        assert resp.status_code == 202
        a.assert_called_once()
        b.assert_called_once()
        c.assert_called_once()
        d.assert_called_once()
        e.assert_called_once()


@pytest.mark.django_db
class TestCounterTasks:
    def test_recompute_tasks_update_dashboard_counter(self):
        Survey.objects.create(id="s1", title="A", status="active", is_deleted=False)
        Survey.objects.create(id="s2", title="B", status="draft", is_deleted=False)
        Offer.objects.create(id="o1", title="A", status="active", is_deleted=False)
        Offer.objects.create(id="o2", title="B", status="inactive", is_deleted=False)

        Response.objects.create(
            survey_id="s1",
            user_id="u1",
            submitted_at=timezone.now(),
            answers=[{"question_id": "q1", "answer_text": "A"}],
            points_earned=10,
        )
        User.objects.create(id="u1", email="u1@b.com", points=50, is_verified=True)
        User.objects.create(id="u2", email="u2@b.com", points=100, is_verified=False)
        Verification.objects.create(
            user_id="u2",
            full_name="User Two",
            mobile_number="0240000000",
            network_provider="MTN",
            id_type="ghana_card",
            id_number="GHA-1",
            id_front_url="https://example.com/front.jpg",
            id_back_url="https://example.com/back.jpg",
            selfie_url="https://example.com/selfie.jpg",
            status="pending",
        )
        Withdrawal.objects.create(
            user_id="u1",
            amount_ghs="10.00",
            points_converted=100,
            recipient_code="RCP_1",
            transfer_reference="REF_1",
            status="completed",
        )
        Withdrawal.objects.create(
            user_id="u2",
            amount_ghs="5.00",
            points_converted=50,
            recipient_code="RCP_2",
            transfer_reference="REF_2",
            status="pending",
        )

        recompute_active_surveys()
        recompute_active_offers()
        recompute_total_responses()
        recompute_total_paid_out()
        recompute_extended_dashboard()

        counter = DashboardCounter.objects.get(id="dashboard")
        assert counter.active_surveys == 1
        assert counter.active_offers == 1
        assert counter.total_responses == 1
        assert float(counter.total_paid_out) == 10.0
        assert counter.total_users == 2
        assert counter.verified_users == 1
        assert counter.total_points_issued == 150
        assert counter.pending_verifications == 1
        assert counter.pending_withdrawals == 1
