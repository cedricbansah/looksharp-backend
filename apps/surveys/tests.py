from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.responses.models import Response
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


@pytest.mark.django_db
class TestAdminSurveyEndpoints:
    def test_admin_create_update_delete_survey(self, mock_firebase):
        admin = User.objects.create(id="admin-survey-1", email="admin-survey-1@b.com", is_admin=True)
        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        create = client.post(
            "/api/v1/admin/surveys/",
            {"title": "Survey A", "status": "draft", "points": 10},
            format="json",
        )
        assert create.status_code == 201
        survey_id = create.data["id"]

        update = client.patch(
            f"/api/v1/admin/surveys/{survey_id}/",
            {"status": "active", "title": "Survey A+"},
            format="json",
        )
        assert update.status_code == 200
        assert update.data["status"] == "active"
        assert update.data["title"] == "Survey A+"

        delete = client.delete(f"/api/v1/admin/surveys/{survey_id}/")
        assert delete.status_code == 204
        assert not Survey.objects.filter(id=survey_id).exists()

    def test_admin_delete_survey_with_responses_returns_409(self, mock_firebase):
        admin = User.objects.create(id="admin-survey-2", email="admin-survey-2@b.com", is_admin=True)
        user = User.objects.create(id="user-survey-2", email="user-survey-2@b.com")
        survey = Survey.objects.create(id="survey-guard-1", title="Guard", status="draft")
        Response.objects.create(
            survey_id=survey.id,
            survey_title=survey.title,
            user_id=user.id,
            user_email=user.email,
            points_earned=0,
            submitted_at=timezone.now(),
            answers=[],
        )

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        resp = client.delete(f"/api/v1/admin/surveys/{survey.id}/")
        assert resp.status_code == 409
        assert Survey.objects.filter(id=survey.id).exists()

    def test_admin_question_create_update_delete_reorder(self, mock_firebase):
        admin = User.objects.create(id="admin-survey-3", email="admin-survey-3@b.com", is_admin=True)
        survey = Survey.objects.create(id="survey-q-1", title="Q Survey", status="draft", question_count=0)

        mock_firebase.return_value = {"uid": admin.id, "email": admin.email}
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")

        q1_resp = client.post(
            f"/api/v1/admin/surveys/{survey.id}/questions/",
            {
                "question_text": "Q1",
                "question_type": "single_select",
                "choices": ["A", "B"],
            },
            format="json",
        )
        assert q1_resp.status_code == 201
        q1_id = q1_resp.data["id"]

        q2_resp = client.post(
            f"/api/v1/admin/surveys/{survey.id}/questions/",
            {
                "question_text": "Q2",
                "question_type": "single_select",
                "choices": ["X", "Y"],
            },
            format="json",
        )
        assert q2_resp.status_code == 201
        q2_id = q2_resp.data["id"]

        survey.refresh_from_db()
        assert survey.question_count == 2

        update_q1 = client.patch(
            f"/api/v1/admin/surveys/{survey.id}/questions/{q1_id}/",
            {"question_text": "Q1 updated"},
            format="json",
        )
        assert update_q1.status_code == 200
        assert update_q1.data["question_text"] == "Q1 updated"

        reorder = client.post(
            f"/api/v1/admin/surveys/{survey.id}/questions/reorder/",
            {"question_a_id": q1_id, "question_b_id": q2_id},
            format="json",
        )
        assert reorder.status_code == 200

        q1 = Question.objects.get(id=q1_id)
        q2 = Question.objects.get(id=q2_id)
        assert q1.position_index != q2.position_index

        delete_q1 = client.delete(f"/api/v1/admin/surveys/{survey.id}/questions/{q1_id}/")
        assert delete_q1.status_code == 204

        survey.refresh_from_db()
        assert survey.question_count == 1

    def test_non_admin_cannot_access_admin_surveys(self, mock_firebase):
        user = User.objects.create(id="member-survey-4", email="member-survey-4@b.com", is_admin=False)
        mock_firebase.return_value = {"uid": user.id, "email": user.email}

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token")
        resp = client.get("/api/v1/admin/surveys/")
        assert resp.status_code == 403
