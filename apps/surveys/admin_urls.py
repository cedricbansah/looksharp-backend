from django.urls import path

from .views import (
    AdminQuestionListCreateView,
    AdminQuestionReorderView,
    AdminQuestionUpdateDeleteView,
    AdminSurveyCategoryListCreateView,
    AdminSurveyCategoryUpdateDeleteView,
    AdminSurveyListCreateView,
    AdminSurveyUpdateDeleteView,
)

urlpatterns = [
    path(
        "survey-categories/",
        AdminSurveyCategoryListCreateView.as_view(),
        name="admin-survey-categories",
    ),
    path(
        "survey-categories/<str:category_id>/",
        AdminSurveyCategoryUpdateDeleteView.as_view(),
        name="admin-survey-categories-detail",
    ),
    path("surveys/", AdminSurveyListCreateView.as_view(), name="admin-surveys"),
    path("surveys/<str:survey_id>/", AdminSurveyUpdateDeleteView.as_view(), name="admin-surveys-detail"),
    path(
        "surveys/<str:survey_id>/questions/",
        AdminQuestionListCreateView.as_view(),
        name="admin-surveys-questions",
    ),
    path(
        "surveys/<str:survey_id>/questions/reorder/",
        AdminQuestionReorderView.as_view(),
        name="admin-surveys-questions-reorder",
    ),
    path(
        "surveys/<str:survey_id>/questions/<str:question_id>/",
        AdminQuestionUpdateDeleteView.as_view(),
        name="admin-surveys-questions-detail",
    ),
]
