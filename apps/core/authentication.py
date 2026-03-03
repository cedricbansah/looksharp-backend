import firebase_admin
from django.conf import settings
from firebase_admin import auth as firebase_auth, credentials
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


def _get_firebase_app():
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
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
