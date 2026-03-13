import pytest
from django.utils import timezone

from apps.core.management.commands.audit_user_email_collisions import (
    _build_collision_report,
    _postgres_reference_counts,
)
from apps.offers.models import Offer, Redemption
from apps.responses.models import Response
from apps.surveys.models import Survey
from apps.users.models import User
from apps.verifications.models import Verification
from apps.withdrawals.models import Withdrawal


@pytest.mark.django_db
def test_build_collision_report_merges_firestore_and_postgres_entries():
    firestore_users = {
        "dup@example.com": [
            {
                "id": "fire-a",
                "created_at": "2026-03-13T00:00:00+00:00",
                "updated_at": "2026-03-13T01:00:00+00:00",
            },
            {
                "id": "shared-id",
                "created_at": "2026-03-12T00:00:00+00:00",
                "updated_at": "2026-03-12T01:00:00+00:00",
            },
        ]
    }
    postgres_users = {
        "dup@example.com": [
            {
                "id": "pg-b",
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T01:00:00+00:00",
            },
            {
                "id": "shared-id",
                "created_at": "2026-03-10T00:00:00+00:00",
                "updated_at": "2026-03-10T01:00:00+00:00",
            },
        ]
    }

    report = _build_collision_report(firestore_users, postgres_users)

    assert len(report) == 1
    assert report[0]["email"] == "dup@example.com"
    assert [entry["id"] for entry in report[0]["uids"]] == ["fire-a", "pg-b", "shared-id"]
    shared = report[0]["uids"][2]
    assert shared["in_firestore"] is True
    assert shared["in_postgres"] is True
    assert shared["firestore"]["created_at"] == "2026-03-12T00:00:00+00:00"
    assert shared["postgres"]["created_at"] == "2026-03-10T00:00:00+00:00"


@pytest.mark.django_db
def test_postgres_reference_counts_cover_all_user_id_tables():
    uid = "canonical-user"
    User.objects.create(id=uid, email="canonical@example.com")
    Survey.objects.create(id="survey-1", title="Survey", created_by=uid)
    Response.objects.create(
        survey_id="survey-1",
        user_id=uid,
        submitted_at=timezone.now(),
        answers=[],
    )
    Verification.objects.create(
        user_id=uid,
        full_name="Canonical User",
        mobile_number="0241234567",
        network_provider="MTN",
        id_type="ghana_card",
        id_number="GHA-123456789-0",
        id_front_url="https://example.com/front.png",
        id_back_url="https://example.com/back.png",
        selfie_url="https://example.com/selfie.png",
    )
    Withdrawal.objects.create(
        user_id=uid,
        amount_ghs="50.00",
        points_converted=500,
        recipient_code="RCP_test",
        transfer_reference="wd_test_reference",
    )
    offer = Offer.objects.create(id="offer-1", title="Offer One")
    Redemption.objects.create(user_id=uid, offer=offer)

    counts = _postgres_reference_counts(uid)

    assert counts == {
        "responses": 1,
        "verifications": 1,
        "withdrawals": 1,
        "redemptions": 1,
        "surveys_created": 1,
    }
