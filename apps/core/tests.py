from types import SimpleNamespace
from unittest.mock import patch

from firebase_admin import auth as firebase_auth
import pytest
from rest_framework.test import APIClient

from apps.core.permissions import IsOwnerOrAdmin
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
def test_health_check_returns_200():
    client = APIClient()
    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "connected"


@pytest.mark.django_db
def test_health_check_returns_503_on_db_failure():
    client = APIClient()
    with patch("apps.core.views.connection.cursor", side_effect=Exception("db unavailable")):
        response = client.get("/api/v1/health/")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "disconnected"


@pytest.mark.django_db
def test_missing_authorization_header_returns_401():
    client = APIClient()
    response = client.get("/api/v1/users/me/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_empty_bearer_token_returns_401():
    client = APIClient()
    response = client.get("/api/v1/users/me/", HTTP_AUTHORIZATION="Bearer ")
    assert response.status_code == 401


@pytest.mark.django_db
def test_revoked_token_returns_401(mock_firebase):
    mock_firebase.side_effect = firebase_auth.RevokedIdTokenError("revoked")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token")
    response = client.get("/api/v1/users/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_expired_token_returns_401(mock_firebase):
    mock_firebase.side_effect = firebase_auth.ExpiredIdTokenError("expired", None)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token")
    response = client.get("/api/v1/users/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_email_backfill_on_existing_user(mock_firebase):
    User.objects.create(id="uid-x", email="")
    mock_firebase.return_value = {"uid": "uid-x", "email": "new@example.com"}

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer token")
    response = client.get("/api/v1/users/me/")

    assert response.status_code == 200
    assert User.objects.get(id="uid-x").email == "new@example.com"


def test_admin_passes_object_permission():
    permission = IsOwnerOrAdmin()
    request = SimpleNamespace(user=SimpleNamespace(id="u1", is_admin=True))
    obj = SimpleNamespace(user_id="someone-else")

    assert permission.has_object_permission(request, None, obj) is True


def test_owner_passes_object_permission():
    permission = IsOwnerOrAdmin()
    request = SimpleNamespace(user=SimpleNamespace(id="u1", is_admin=False))
    obj = SimpleNamespace(user_id="u1")

    assert permission.has_object_permission(request, None, obj) is True


def test_non_owner_denied_object_permission():
    permission = IsOwnerOrAdmin()
    request = SimpleNamespace(user=SimpleNamespace(id="u1", is_admin=False))
    obj = SimpleNamespace(user_id="u2")

    assert permission.has_object_permission(request, None, obj) is False
