from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def mock_firebase():
    """Patch firebase_auth.verify_id_token for all tests."""
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mock_verify, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mock_verify


@pytest.mark.django_db
class TestMeEndpoint:
    def test_get_me_returns_profile(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-1", "email": "a@b.com"}
        User.objects.create(id="uid-1", email="a@b.com", points=100)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.data["email"] == "a@b.com"
        assert response.data["points"] == 100

    def test_get_me_creates_user_on_first_login(self, mock_firebase):
        mock_firebase.return_value = {"uid": "new-uid", "email": "new@example.com"}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert User.objects.filter(id="new-uid").exists()

    def test_patch_me_updates_writable_fields(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-2", "email": "b@b.com"}
        User.objects.create(id="uid-2", email="b@b.com")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.patch("/api/v1/users/me/", {"first_name": "Kofi"}, format="json")
        assert response.status_code == 200
        assert User.objects.get(id="uid-2").first_name == "Kofi"

    def test_patch_me_cannot_write_server_controlled_fields(self, mock_firebase):
        mock_firebase.return_value = {"uid": "uid-3", "email": "c@c.com"}
        User.objects.create(id="uid-3", email="c@c.com", points=50)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        response = client.patch("/api/v1/users/me/", {"points": 9999}, format="json")
        assert response.status_code == 200
        assert User.objects.get(id="uid-3").points == 50

    def test_get_me_without_token_returns_401(self):
        client = APIClient()
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self):
        with patch("apps.core.authentication.firebase_auth.verify_id_token") as mock_verify, patch(
            "apps.core.authentication._get_firebase_app"
        ):
            mock_verify.side_effect = Exception("invalid token")
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION="Bearer bad-token")
            response = client.get("/api/v1/users/me/")
            assert response.status_code == 401
