import base64
import json
import os
import tempfile

import firebase_admin
from django.conf import settings
from firebase_admin import auth as firebase_auth, credentials
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


def _get_firebase_credentials():
    """
    Load Firebase credentials from either:
    1. FIREBASE_SERVICE_ACCOUNT_JSON env var (base64-encoded JSON) - for PaaS like Railway
    2. FIREBASE_SERVICE_ACCOUNT_KEY_PATH setting (file path) - for traditional deployments
    """
    # Option 1: Base64-encoded JSON in environment variable (Railway, Heroku, etc.)
    b64_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if b64_json:
        try:
            json_bytes = base64.b64decode(b64_json)
            service_account_info = json.loads(json_bytes)
            return credentials.Certificate(service_account_info)
        except Exception as e:
            raise ValueError(f"Failed to decode FIREBASE_SERVICE_ACCOUNT_JSON: {e}")

    # Option 2: File path (GCP, local development)
    key_path = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_KEY_PATH", None)
    if key_path:
        return credentials.Certificate(key_path)

    raise ValueError(
        "Firebase credentials not configured. Set either "
        "FIREBASE_SERVICE_ACCOUNT_JSON (base64) or FIREBASE_SERVICE_ACCOUNT_KEY_PATH."
    )


def _get_firebase_app():
    if not firebase_admin._apps:
        cred = _get_firebase_credentials()
        firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


def _resolved_email(decoded_token: dict) -> str:
    """Ensure every Firebase user can be persisted with a unique, stable email value."""
    email = decoded_token.get("email")
    if email:
        return email
    uid = decoded_token["uid"]
    return f"{uid}@firebase.local"


class FirebaseAuthentication(BaseAuthentication):
    """
    Verify a Firebase ID token from the Authorization header.
    Resolves or creates a User row in Postgres keyed by Firebase UID.
    Returns (user, None) on success; raises AuthenticationFailed on bad token.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        id_token = auth_header.split("Bearer ", 1)[1].strip()
        if not id_token:
            return None

        try:
            _get_firebase_app()
            decoded = firebase_auth.verify_id_token(id_token)
        except firebase_auth.RevokedIdTokenError as exc:
            raise AuthenticationFailed("Firebase token has been revoked.") from exc
        except firebase_auth.ExpiredIdTokenError as exc:
            raise AuthenticationFailed("Firebase token has expired.") from exc
        except Exception as exc:
            raise AuthenticationFailed("Invalid Firebase token.") from exc

        uid = decoded["uid"]
        email = _resolved_email(decoded)

        from apps.users.models import User

        user, _ = User.objects.get_or_create(
            id=uid,
            defaults={"email": email, "points": 0},
        )
        if not user.email:
            user.email = email
            user.save(update_fields=["email", "updated_at"])
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"
