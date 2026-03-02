# Phase 2 Plan: Core Business Flows (Reward Path + Payout Path)

## Context

Phase 2 implements the two P0 flows from the migration matrix — the ones that touch money
and data integrity. Both must be idempotent. Neither can have bugs.

**Reward path** — replaces `response-count-function`:
- `POST /api/v1/responses/` creates a response record and fires an async Celery task
- The task increments `survey.response_count`, `user.points`, and appends to
  `user.surveys_completed` in a single DB transaction, guarded by a duplicate check

**Payout path** — replaces `paystack-approval-function` + `pstkLsPrivateCallsV2`:
- `POST /api/v1/withdrawals/` records a pending withdrawal
- `POST /api/v1/webhooks/paystack/` handles Paystack transfer approval/decline
  (HMAC-verified, mirrors the existing Cloud Function logic exactly)
- `/api/v1/paystack/*` endpoints proxy Paystack calls server-side
  (removes the secret key from the mobile build entirely)

**Source files being ported:**
- `looksharp-functions/response-count-function/main.py`
- `looksharp-functions/paystack-approval-function/main.py`
- `looksharp-functions/tests/test_response_count.py` (test cases ported)
- `looksharp-functions/tests/test_paystack_approval.py` (test cases ported)

---

## Files to create / modify

| File | Action |
|---|---|
| `apps/surveys/models.py` | Create minimal Survey model (needed by reward task) |
| `apps/responses/models.py` | Create Response model |
| `apps/responses/serializers.py` | ResponseCreateSerializer, ResponseListSerializer |
| `apps/responses/views.py` | POST + GET /api/v1/responses/ |
| `apps/responses/tasks.py` | apply_side_effects Celery task |
| `apps/responses/urls.py` | Wire up views |
| `apps/responses/tests.py` | Tests |
| `apps/withdrawals/models.py` | Create Withdrawal model |
| `apps/withdrawals/serializers.py` | WithdrawalCreateSerializer, WithdrawalListSerializer |
| `apps/withdrawals/views.py` | POST + GET /api/v1/withdrawals/ |
| `apps/withdrawals/urls.py` | Wire up views |
| `apps/withdrawals/tests.py` | Tests |
| `apps/webhooks/views.py` | POST /api/v1/webhooks/paystack/ |
| `apps/webhooks/urls.py` | Wire up view |
| `apps/webhooks/tests.py` | Tests |
| `apps/paystack/views.py` | 4 typed proxy endpoints |
| `apps/paystack/urls.py` | Wire up views |
| `apps/paystack/tests.py` | Tests |
| `services/paystack.py` | Full implementation (was stub) |

---

## Step 1 — Minimal Survey model

The reward task needs `survey.points` and must increment `survey.response_count`.
Full surveys CRUD comes in Phase 3. For now, just the fields the task requires.

**`apps/surveys/models.py`**
```python
from django.db import models


class Survey(models.Model):
    id = models.CharField(max_length=128, primary_key=True)  # Firestore doc ID
    title = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, default="draft")
    points = models.PositiveIntegerField(default=0)
    response_count = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "surveys"

    def __str__(self):
        return self.title or self.id
```

Add `"apps.surveys"` to INSTALLED_APPS (already listed in base.py from Phase 1).
Run `python manage.py makemigrations surveys`.

---

## Step 2 — Response model

**`apps/responses/models.py`**
```python
import uuid
from django.db import models


class Response(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survey_id = models.CharField(max_length=128, db_index=True)
    survey_title = models.CharField(max_length=500, blank=True)
    user_id = models.CharField(max_length=128, db_index=True)
    user_email = models.EmailField(blank=True)
    points_earned = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField()
    # Embedded answers array — matches Firestore contract exactly
    # [{question_id, question_text, position_index, answer_text}, ...]
    answers = models.JSONField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "responses"
        # DB-level safety net — task also checks surveys_completed for idempotency
        unique_together = [("user_id", "survey_id")]

    def __str__(self):
        return f"Response {self.id} — survey {self.survey_id} by {self.user_id}"
```

Run `python manage.py makemigrations responses`.

---

## Step 3 — Response serializers

**`apps/responses/serializers.py`**
```python
from rest_framework import serializers
from .models import Response


class AnswerSerializer(serializers.Serializer):
    question_id = serializers.CharField()
    question_text = serializers.CharField(allow_blank=True, default="")
    position_index = serializers.IntegerField(default=0)
    answer_text = serializers.CharField(allow_blank=True, default="")


class ResponseCreateSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True)

    class Meta:
        model = Response
        fields = [
            "survey_id", "survey_title", "user_id", "user_email",
            "points_earned", "submitted_at", "answers",
        ]

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("answers must not be empty.")
        return value


class ResponseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = [
            "id", "survey_id", "survey_title", "user_id", "user_email",
            "points_earned", "submitted_at", "answers", "is_deleted", "created_at",
        ]
        read_only_fields = fields
```

---

## Step 4 — Response views + URLs

**`apps/responses/views.py`**
```python
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse
from .models import Response
from .serializers import ResponseCreateSerializer, ResponseListSerializer
from .tasks import apply_side_effects


class ResponseListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/responses/  — submit a survey response
    GET  /api/v1/responses/  — list the authenticated user's responses
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Response.objects.filter(
            user_id=self.request.user.id,
            is_deleted=False,
        ).order_by("-submitted_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ResponseCreateSerializer
        return ResponseListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_obj = serializer.save()
        # Fire side-effects task asynchronously on the critical queue
        apply_side_effects.apply_async(
            args=[response_obj.survey_id, response_obj.user_id],
            queue="critical",
        )
        return DRFResponse(
            ResponseListSerializer(response_obj).data,
            status=status.HTTP_201_CREATED,
        )
```

**`apps/responses/urls.py`**
```python
from django.urls import path
from .views import ResponseListCreateView

urlpatterns = [
    path("", ResponseListCreateView.as_view(), name="responses"),
]
```

---

## Step 5 — Response reward task

This is the direct port of `_process_response()` from `response-count-function/main.py`,
translated from Firestore transactions to Django's `select_for_update()` + `F()` expressions.

**`apps/responses/tasks.py`**
```python
import logging
from celery import shared_task
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="critical", max_retries=3,
             autoretry_for=(Exception,), retry_backoff=True)
def apply_side_effects(self, survey_id: str, user_id: str) -> None:
    """
    Idempotent task: award points and increment counters after a survey response.

    Mirrors the logic of response-count-function/main.py _process_response().
    Uses select_for_update() for row-level locking (Postgres equivalent of
    a Firestore transaction).
    """
    from apps.surveys.models import Survey
    from apps.users.models import User

    with transaction.atomic():
        try:
            survey = Survey.objects.select_for_update().get(id=survey_id)
        except Survey.DoesNotExist:
            logger.warning(f"Survey {survey_id} not found — skipping reward")
            return

        try:
            user = User.objects.select_for_update().get(id=user_id)
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found — skipping reward")
            return

        # Idempotency guard — mirrors surveys_completed check in the Cloud Function
        if survey_id in (user.surveys_completed or []):
            logger.info(
                f"Duplicate reward skipped: user {user_id} already completed survey {survey_id}"
            )
            return

        points = survey.points if isinstance(survey.points, int) else 0

        # Atomic increment — equivalent of Firestore Increment + ArrayUnion
        Survey.objects.filter(id=survey_id).update(response_count=F("response_count") + 1)
        User.objects.filter(id=user_id).update(
            points=F("points") + points,
            surveys_completed=user.surveys_completed + [survey_id],
        )

        logger.info(
            f"Reward applied: survey={survey_id} user={user_id} points={points}"
        )
```

---

## Step 6 — Withdrawal model

**`apps/withdrawals/models.py`**
```python
import uuid
from django.db import models

WITHDRAWAL_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("processing", "Processing"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]


class Withdrawal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=128, db_index=True)
    amount_ghs = models.DecimalField(max_digits=10, decimal_places=2)
    points_converted = models.PositiveIntegerField()
    recipient_code = models.CharField(max_length=100)
    # Unique logical key — enforces idempotency at DB level
    transfer_reference = models.CharField(max_length=200, unique=True)
    transfer_code = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20, default="pending", choices=WITHDRAWAL_STATUS_CHOICES
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "withdrawals"

    def __str__(self):
        return f"Withdrawal {self.id} — {self.status} — {self.amount_ghs} GHS"
```

Run `python manage.py makemigrations withdrawals`.

---

## Step 7 — Withdrawal serializers

**`apps/withdrawals/serializers.py`**
```python
from decimal import Decimal
from rest_framework import serializers
from .models import Withdrawal

MINIMUM_AMOUNT_GHS = Decimal("5.00")


class WithdrawalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "amount_ghs", "points_converted", "recipient_code", "transfer_reference",
        ]

    def validate_amount_ghs(self, value):
        if value < MINIMUM_AMOUNT_GHS:
            raise serializers.ValidationError(
                f"Minimum withdrawal amount is GHS {MINIMUM_AMOUNT_GHS}."
            )
        return value

    def validate_points_converted(self, value):
        if value <= 0:
            raise serializers.ValidationError("points_converted must be greater than 0.")
        return value


class WithdrawalListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = [
            "id", "user_id", "amount_ghs", "points_converted", "recipient_code",
            "transfer_reference", "transfer_code", "status", "failure_reason",
            "created_at", "updated_at", "completed_at",
        ]
        read_only_fields = fields
```

---

## Step 8 — Withdrawal views + URLs

**`apps/withdrawals/views.py`**
```python
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response as DRFResponse
from apps.core.permissions import IsVerified
from .models import Withdrawal
from .serializers import WithdrawalCreateSerializer, WithdrawalListSerializer


class WithdrawalListCreateView(generics.ListCreateAPIView):
    """
    POST /api/v1/withdrawals/  — create a pending withdrawal (user must be verified)
    GET  /api/v1/withdrawals/  — list the authenticated user's withdrawals
    """
    permission_classes = [IsAuthenticated, IsVerified]

    def get_queryset(self):
        return Withdrawal.objects.filter(
            user_id=self.request.user.id,
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WithdrawalCreateSerializer
        return WithdrawalListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = serializer.save(user_id=request.user.id, status="pending")
        return DRFResponse(
            WithdrawalListSerializer(withdrawal).data,
            status=status.HTTP_201_CREATED,
        )
```

**`apps/withdrawals/urls.py`**
```python
from django.urls import path
from .views import WithdrawalListCreateView

urlpatterns = [
    path("", WithdrawalListCreateView.as_view(), name="withdrawals"),
]
```

---

## Step 9 — Paystack service (full implementation)

**`services/paystack.py`**
```python
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)
PAYSTACK_BASE = "https://api.paystack.co"


def _headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _request(method, path, **kwargs):
    """Make a Paystack API call. Raises requests.HTTPError on non-2xx."""
    url = f"{PAYSTACK_BASE}{path}"
    response = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def list_banks(type="mobile_money", currency="GHS"):
    return _request("GET", "/bank", params={"type": type, "currency": currency})


def create_transfer_recipient(name, account_number, bank_code,
                               type="mobile_money", currency="GHS"):
    return _request("POST", "/transferrecipient", json={
        "type": type,
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": currency,
    })


def initiate_transfer(recipient, amount_kobo, reference, reason="LookSharp cashout"):
    """amount_kobo: amount in kobo (pesewas for GHS). 1 GHS = 100 kobo."""
    return _request("POST", "/transfer", json={
        "source": "balance",
        "recipient": recipient,
        "amount": amount_kobo,
        "reference": reference,
        "reason": reason,
    })


def finalize_transfer(transfer_code):
    return _request("POST", "/transfer/finalize_transfer", json={
        "transfer_code": transfer_code,
    })
```

---

## Step 10 — Paystack proxy views + URLs

**`apps/paystack/views.py`**
```python
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests as http_requests
import services.paystack as paystack_service

logger = logging.getLogger(__name__)


class BanksView(APIView):
    """GET /api/v1/paystack/banks/ — list telcos/banks"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = paystack_service.list_banks(
                type=request.query_params.get("type", "mobile_money"),
                currency=request.query_params.get("currency", "GHS"),
            )
            return Response(data)
        except http_requests.HTTPError as e:
            logger.error(f"Paystack list_banks failed: {e}")
            return Response({"error": "Paystack request failed"}, status=status.HTTP_502_BAD_GATEWAY)


class TransferRecipientsView(APIView):
    """POST /api/v1/paystack/transfer-recipients/ — create a transfer recipient"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = paystack_service.create_transfer_recipient(
                name=request.data["name"],
                account_number=request.data["account_number"],
                bank_code=request.data["bank_code"],
                type=request.data.get("type", "mobile_money"),
                currency=request.data.get("currency", "GHS"),
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except KeyError as e:
            return Response({"error": f"Missing field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.HTTPError as e:
            logger.error(f"Paystack create_recipient failed: {e}")
            return Response({"error": "Paystack request failed"}, status=status.HTTP_502_BAD_GATEWAY)


class TransfersView(APIView):
    """POST /api/v1/paystack/transfers/ — initiate a transfer"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = paystack_service.initiate_transfer(
                recipient=request.data["recipient"],
                amount_kobo=request.data["amount"],
                reference=request.data["reference"],
                reason=request.data.get("reason", "LookSharp cashout"),
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except KeyError as e:
            return Response({"error": f"Missing field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.HTTPError as e:
            logger.error(f"Paystack initiate_transfer failed: {e}")
            return Response({"error": "Paystack request failed"}, status=status.HTTP_502_BAD_GATEWAY)


class FinalizeTransferView(APIView):
    """POST /api/v1/paystack/transfers/{code}/finalize/ — finalize a transfer"""
    permission_classes = [IsAuthenticated]

    def post(self, request, transfer_code):
        try:
            data = paystack_service.finalize_transfer(transfer_code)
            return Response(data)
        except http_requests.HTTPError as e:
            logger.error(f"Paystack finalize_transfer failed: {e}")
            return Response({"error": "Paystack request failed"}, status=status.HTTP_502_BAD_GATEWAY)
```

**`apps/paystack/urls.py`**
```python
from django.urls import path
from .views import BanksView, TransferRecipientsView, TransfersView, FinalizeTransferView

urlpatterns = [
    path("banks/", BanksView.as_view(), name="paystack-banks"),
    path("transfer-recipients/", TransferRecipientsView.as_view(), name="paystack-recipients"),
    path("transfers/", TransfersView.as_view(), name="paystack-transfers"),
    path("transfers/<str:transfer_code>/finalize/", FinalizeTransferView.as_view(),
         name="paystack-finalize"),
]
```

---

## Step 11 — Paystack webhook view

Direct port of `paystack-approval-function/main.py`. The HMAC logic is identical.
Key difference: reads `request.body` (raw bytes) before DRF parses — same as
`request.get_data()` in the Cloud Function.

**`apps/webhooks/views.py`**
```python
import hashlib
import hmac
import json
import logging
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    """HMAC SHA512 verification — identical to the Cloud Function."""
    if not signature or not settings.PAYSTACK_SECRET_KEY:
        return False
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _extract_transfer_details(data: dict):
    """Extract transfer_code + reference from 3 Paystack payload formats."""
    if "transfer_code" in data:
        return data.get("transfer_code"), data.get("reference")
    if data.get("event") == "transferrequest.approval-required":
        transfers = data.get("data", {}).get("transfers", [])
        if transfers:
            return transfers[0].get("transfer_code"), transfers[0].get("reference")
        return None, None
    if "data" in data and "transfer_code" in data.get("data", {}):
        return data["data"]["transfer_code"], data["data"].get("reference")
    return None, None


class PaystackWebhookView(APIView):
    """
    POST /api/v1/webhooks/paystack/
    Handles Paystack transfer approval/decline events.
    No auth — HMAC signature is the authentication mechanism.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Read raw bytes BEFORE any parsing (required for HMAC)
        raw_body = request.body
        if not raw_body:
            return Response({"error": "Empty body"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Verify Paystack signature
        signature = request.headers.get("X-Paystack-Signature", "")
        if not _verify_signature(raw_body, signature):
            logger.warning("Paystack webhook: invalid signature")
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        # 3. Parse JSON
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Extract transfer identifiers
        transfer_code, reference = _extract_transfer_details(data)
        if not transfer_code and not reference:
            logger.warning(f"Paystack webhook: no identifiers in event {data.get('event')}")
            return Response({"error": "Missing transfer identifiers"},
                            status=status.HTTP_400_BAD_REQUEST)

        # 5. Validate and transition withdrawal state
        identifier = reference or transfer_code
        identifier_type = "transfer_reference" if reference else "transfer_code"

        result = _validate_and_transition(identifier, identifier_type, transfer_code)

        if result["success"]:
            return Response({}, status=status.HTTP_200_OK)
        else:
            return Response({"error": result["reason"]}, status=status.HTTP_400_BAD_REQUEST)


def _validate_and_transition(identifier, identifier_type, transfer_code):
    """
    Validate withdrawal and transition its status.
    Mirrors validate_transfer_request() + update_withdrawal_status() from the Cloud Function.
    """
    from apps.withdrawals.models import Withdrawal
    from apps.users.models import User

    try:
        withdrawal = Withdrawal.objects.filter(**{identifier_type: identifier}).first()
        if not withdrawal:
            logger.error(f"Withdrawal not found: {identifier_type}={identifier}")
            return {"success": False, "reason": "Transfer not found"}

        user = User.objects.filter(id=withdrawal.user_id).first()
        if not user:
            _mark_failed(withdrawal, transfer_code, "User not found")
            return {"success": False, "reason": "User not found"}

        if not user.is_verified:
            _mark_failed(withdrawal, transfer_code, "User not verified")
            return {"success": False, "reason": "User not verified"}

        if withdrawal.status not in ("pending", "processing"):
            reason = f"Invalid withdrawal status: {withdrawal.status}"
            _mark_failed(withdrawal, transfer_code, reason)
            return {"success": False, "reason": reason}

        if withdrawal.points_converted > user.points:
            _mark_failed(withdrawal, transfer_code, "Insufficient points")
            return {"success": False, "reason": "Insufficient points"}

        pending_count = Withdrawal.objects.filter(
            user_id=withdrawal.user_id,
            status__in=["pending", "processing"],
        ).count()
        if pending_count > 1:
            _mark_failed(withdrawal, transfer_code, "Multiple pending withdrawals")
            return {"success": False, "reason": "Multiple pending withdrawals"}

        # All checks passed — approve
        withdrawal.status = "processing"
        if transfer_code:
            withdrawal.transfer_code = transfer_code
        withdrawal.updated_at = timezone.now()
        withdrawal.save(update_fields=["status", "transfer_code", "updated_at"])

        logger.info(f"Withdrawal {withdrawal.id} approved → processing")
        return {"success": True}

    except Exception as e:
        logger.exception(f"Error in webhook validation: {e}")
        return {"success": False, "reason": "Internal error"}


def _mark_failed(withdrawal, transfer_code, reason):
    from django.utils import timezone
    withdrawal.status = "failed"
    withdrawal.failure_reason = reason
    if transfer_code:
        withdrawal.transfer_code = transfer_code
    withdrawal.updated_at = timezone.now()
    withdrawal.save(update_fields=["status", "failure_reason", "transfer_code", "updated_at"])
    logger.warning(f"Withdrawal {withdrawal.id} → failed: {reason}")
```

**`apps/webhooks/urls.py`**
```python
from django.urls import path
from .views import PaystackWebhookView

urlpatterns = [
    path("paystack/", PaystackWebhookView.as_view(), name="webhook-paystack"),
]
```

---

## Step 12 — Tests

### `apps/responses/tests.py`
```python
import pytest
from unittest.mock import patch
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import User
from apps.surveys.models import Survey
from apps.responses.models import Response
from apps.responses.tasks import apply_side_effects


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as m, \
         patch("apps.core.authentication._get_firebase_app"):
        yield m


@pytest.mark.django_db
class TestResponseEndpoint:

    def test_post_response_returns_201(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Survey.objects.create(id="s1", title="Test", points=25)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        payload = {
            "survey_id": "s1", "submitted_at": timezone.now().isoformat(),
            "answers": [{"question_id": "q1", "question_text": "Q1",
                         "position_index": 0, "answer_text": "A"}],
            "user_id": "u1",
        }
        with patch("apps.responses.views.apply_side_effects.apply_async"):
            resp = client.post("/api/v1/responses/", payload, format="json")
        assert resp.status_code == 201

    def test_post_response_without_auth_returns_401(self):
        client = APIClient()
        resp = client.post("/api/v1/responses/", {}, format="json")
        assert resp.status_code == 401

    def test_get_responses_returns_only_own(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com")
        Response.objects.create(
            survey_id="s1", user_id="u2", submitted_at=timezone.now(),
            answers=[], points_earned=10,
        )
        Response.objects.create(
            survey_id="s2", user_id="other-user", submitted_at=timezone.now(),
            answers=[], points_earned=10,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/responses/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1


@pytest.mark.django_db
class TestApplySideEffects:

    def test_awards_points_from_survey(self):
        Survey.objects.create(id="s1", points=25, response_count=0)
        User.objects.create(id="u1", email="a@b.com", points=50, surveys_completed=[])
        apply_side_effects("s1", "u1")
        user = User.objects.get(id="u1")
        assert user.points == 75
        assert "s1" in user.surveys_completed
        survey = Survey.objects.get(id="s1")
        assert survey.response_count == 1

    def test_duplicate_skipped(self):
        Survey.objects.create(id="s1", points=25, response_count=5)
        User.objects.create(id="u1", email="a@b.com", points=100, surveys_completed=["s1"])
        apply_side_effects("s1", "u1")
        user = User.objects.get(id="u1")
        assert user.points == 100  # unchanged
        survey = Survey.objects.get(id="s1")
        assert survey.response_count == 5  # unchanged

    def test_missing_survey_does_not_raise(self):
        User.objects.create(id="u1", email="a@b.com", points=0, surveys_completed=[])
        apply_side_effects("nonexistent", "u1")  # should not raise

    def test_authoritative_points_from_survey_not_payload(self):
        Survey.objects.create(id="s1", points=40, response_count=0)
        User.objects.create(id="u1", email="a@b.com", points=0, surveys_completed=[])
        apply_side_effects("s1", "u1")
        assert User.objects.get(id="u1").points == 40
```

### `apps/webhooks/tests.py`
```python
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
            user_id="u1", amount_ghs="10.00", points_converted=100,
            recipient_code="RCP_1", transfer_reference="REF_1", status="pending",
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
            "/api/v1/webhooks/paystack/", data=raw,
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
```

### `apps/withdrawals/tests.py`
```python
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from apps.users.models import User
from apps.withdrawals.models import Withdrawal


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as m, \
         patch("apps.core.authentication._get_firebase_app"):
        yield m


@pytest.mark.django_db
class TestWithdrawalEndpoint:

    def test_verified_user_can_create_withdrawal(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com", is_verified=True, points=500)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/withdrawals/", {
            "amount_ghs": "10.00", "points_converted": 100,
            "recipient_code": "RCP_1", "transfer_reference": "REF_unique_1",
        }, format="json")
        assert resp.status_code == 201
        assert Withdrawal.objects.filter(user_id="u1").count() == 1

    def test_unverified_user_gets_403(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com", is_verified=False)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/withdrawals/", {
            "amount_ghs": "10.00", "points_converted": 100,
            "recipient_code": "RCP_1", "transfer_reference": "REF_2",
        }, format="json")
        assert resp.status_code == 403

    def test_below_minimum_amount_returns_400(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u3", "email": "c@c.com"}
        User.objects.create(id="u3", email="c@c.com", is_verified=True)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.post("/api/v1/withdrawals/", {
            "amount_ghs": "2.00", "points_converted": 20,
            "recipient_code": "RCP_1", "transfer_reference": "REF_3",
        }, format="json")
        assert resp.status_code == 400
```

---

## Step 13 — Run migrations + commit

```bash
python manage.py makemigrations surveys responses withdrawals
python manage.py migrate
```

```bash
git add .
git commit -m "Phase 2: responses reward path and payout path (webhook + withdrawals + paystack proxy)"
```

---

## Verification Checklist

```bash
python manage.py check          # no issues
python manage.py migrate        # clean
pytest apps/responses/tests.py apps/withdrawals/tests.py apps/webhooks/tests.py -v
# all tests pass
```

Manual smoke tests (with real Firebase token + Paystack test key):
```bash
# Submit a response
curl -X POST /api/v1/responses/ -H "Authorization: Bearer <token>" \
  -d '{"survey_id":"s1","submitted_at":"...","answers":[...],"user_id":"uid"}'
# → 201

# Paystack webhook (simulate approval)
python -c "
import hmac, hashlib, json
payload = json.dumps({'reference':'REF_1'}).encode()
sig = hmac.new(b'<secret>', payload, hashlib.sha512).hexdigest()
print(sig)
"
curl -X POST /api/v1/webhooks/paystack/ \
  -H "X-Paystack-Signature: <sig>" -d '{"reference":"REF_1"}'
# → 200

# Unauth on protected endpoint
curl /api/v1/withdrawals/ → 401
```
