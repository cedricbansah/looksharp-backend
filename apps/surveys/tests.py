from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.surveys.models import Question, Survey
from apps.users.models import User


@pytest.fixture
def mock_firebase():
    with patch("apps.core.authentication.firebase_auth.verify_id_token") as mocked, patch(
        "apps.core.authentication._get_firebase_app"
    ):
        yield mocked


@pytest.mark.django_db
class TestSurveyEndpoints:
    def test_list_returns_active_surveys_only(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u1", "email": "a@b.com"}
        User.objects.create(id="u1", email="a@b.com")
        Survey.objects.create(id="s1", title="Active", status="active", is_deleted=False)
        Survey.objects.create(id="s2", title="Draft", status="draft", is_deleted=False)
        Survey.objects.create(id="s3", title="Deleted", status="active", is_deleted=True)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/surveys/")

        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["id"] == "s1"

    def test_detail_includes_questions(self, mock_firebase):
        mock_firebase.return_value = {"uid": "u2", "email": "b@b.com"}
        User.objects.create(id="u2", email="b@b.com")
        survey = Survey.objects.create(id="s1", title="Active", status="active", is_deleted=False)
        Question.objects.create(
            survey=survey,
            question_text="How are you?",
            question_type="text",
            position_index=0,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/surveys/s1/")

        assert resp.status_code == 200
        assert resp.data["id"] == "s1"
        assert len(resp.data["questions"]) == 1
        assert resp.data["questions"][0]["question_text"] == "How are you?"

    def test_list_requires_auth(self):
        client = APIClient()
        resp = client.get("/api/v1/surveys/")
        assert resp.status_code == 401
