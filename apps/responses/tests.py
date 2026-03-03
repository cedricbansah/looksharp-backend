from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.responses.models import Response
from apps.responses.tasks import apply_side_effects
from apps.surveys.models import Survey
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestResponseEndpoint:
    def test_post_response_returns_201(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Survey.objects.create(id="s1", title="Test", points=25)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        payload = {
            "survey_id": "s1",
            "submitted_at": timezone.now().isoformat(),
            "answers": [
                {
                    "question_id": "q1",
                    "question_text": "Q1",
                    "position_index": 0,
                    "answer_text": "A",
                }
            ],
            "user_id": "u1",
        }
        with patch("apps.responses.views.apply_side_effects.apply_async"):
            resp = client.post("/api/v1/responses/", payload, format="json")
        assert resp.status_code == 201
        created = Response.objects.get()
        assert created.user_id == "u1"
        assert created.points_earned == 25

    def test_post_response_without_auth_returns_401(self):
        client = APIClient()
        resp = client.post("/api/v1/responses/", {}, format="json")
        assert resp.status_code == 401

    def test_get_responses_returns_only_own(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com")
        Response.objects.create(
            survey_id="s1",
            user_id="u2",
            submitted_at=timezone.now(),
            answers=[],
            points_earned=10,
        )
        Response.objects.create(
            survey_id="s2",
            user_id="other-user",
            submitted_at=timezone.now(),
            answers=[],
            points_earned=10,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/responses/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1

    def test_post_response_ignores_spoofed_identity_fields(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "real@b.com"}
        User.objects.create(id="u1", email="real@b.com")
        Survey.objects.create(id="s1", title="Test", points=25)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        payload = {
            "survey_id": "s1",
            "submitted_at": timezone.now().isoformat(),
            "answers": [{"question_id": "q1", "answer_text": "A"}],
            "user_id": "attacker-id",
            "user_email": "spoofed@example.com",
            "points_earned": 999999,
        }
        with patch("apps.responses.views.apply_side_effects.apply_async"):
            resp = client.post("/api/v1/responses/", payload, format="json")
        assert resp.status_code == 201
        created = Response.objects.get()
        assert created.user_id == "u1"
        assert created.user_email == "real@b.com"
        assert created.points_earned == 25

    def test_duplicate_response_returns_409(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Survey.objects.create(id="s1", title="Test", points=25)
        Response.objects.create(
            survey_id="s1",
            user_id="u1",
            user_email="a@b.com",
            submitted_at=timezone.now(),
            answers=[{"question_id": "q1", "answer_text": "A"}],
            points_earned=25,
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        with patch("apps.responses.views.apply_side_effects.apply_async"):
            resp = client.post(
                "/api/v1/responses/",
                {
                    "survey_id": "s1",
                    "submitted_at": timezone.now().isoformat(),
                    "answers": [{"question_id": "q1", "answer_text": "B"}],
                },
                format="json",
            )
        assert resp.status_code == 400


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
        assert user.points == 100
        survey = Survey.objects.get(id="s1")
        assert survey.response_count == 5

    def test_missing_survey_does_not_raise(self):
        User.objects.create(id="u1", email="a@b.com", points=0, surveys_completed=[])
        apply_side_effects("nonexistent", "u1")

    def test_authoritative_points_from_survey_not_payload(self):
        Survey.objects.create(id="s1", points=40, response_count=0)
        User.objects.create(id="u1", email="a@b.com", points=0, surveys_completed=[])
        apply_side_effects("s1", "u1")
        assert User.objects.get(id="u1").points == 40


@pytest.mark.django_db
class TestAdminResponseEndpoint:
    def test_admin_can_filter_responses_by_survey_id(self, mock_firebase):
        mock_firebase.return_value = {"uid": "admin-1", "email": "admin@looksharp.co"}
        User.objects.create(id="admin-1", email="admin@looksharp.co", is_admin=True)
        Response.objects.create(
            survey_id="s1",
            user_id="u1",
            submitted_at=timezone.now(),
            answers=[],
            points_earned=10,
        )
        Response.objects.create(
            survey_id="s2",
            user_id="u2",
            submitted_at=timezone.now(),
            answers=[],
            points_earned=20,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/admin/responses/?survey_id=s1")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["survey_id"] == "s1"
