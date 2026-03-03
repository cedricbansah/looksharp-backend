from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.offers.models import Offer, Redemption
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestOfferEndpoints:
    def test_list_returns_active_offers(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Offer.objects.create(id="o1", title="A", status="active", is_deleted=False)
        Offer.objects.create(id="o2", title="B", status="inactive", is_deleted=False)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/offers/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["id"] == "o1"

    def test_redeem_offer_deducts_points(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com", points=200)
        Offer.objects.create(
            id="o1",
            title="Offer",
            status="active",
            points_required=100,
            client_name="Client",
            offer_code="CODE1",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")

        assert resp.status_code == 201
        assert Redemption.objects.filter(user_id="u2", offer_id="o1").count() == 1
        assert User.objects.get(id="u2").points == 100

    def test_redeem_offer_is_idempotent(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@b.com"}
        User.objects.create(id="u3", email="c@b.com", points=200)
        Offer.objects.create(
            id="o2",
            title="Offer",
            status="active",
            points_required=100,
            client_name="Client",
            offer_code="CODE2",
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        first = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")
        second = client.post("/api/v1/redemptions/", {"offer_id": "o2"}, format="json")

        assert first.status_code == 201
        assert second.status_code == 200
        assert Redemption.objects.filter(user_id="u3", offer_id="o2").count() == 1
        assert User.objects.get(id="u3").points == 100

    def test_redeem_offer_insufficient_points_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u4", "email": "d@b.com"}
        User.objects.create(id="u4", email="d@b.com", points=10)
        Offer.objects.create(id="o3", title="Offer", status="active", points_required=100)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o3"}, format="json")

        assert resp.status_code == 400

    def test_redeem_requires_auth(self):
        client = APIClient()
        resp = client.post("/api/v1/redemptions/", {"offer_id": "o1"}, format="json")
        assert resp.status_code == 401
