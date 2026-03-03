from django.urls import path

from .views import SurveyDetailView, SurveyListView

urlpatterns = [
    path("", SurveyListView.as_view(), name="surveys-list"),
    path("<str:pk>/", SurveyDetailView.as_view(), name="surveys-detail"),
]
