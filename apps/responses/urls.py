from django.urls import path

from .views import ResponseDetailView, ResponseListCreateView

urlpatterns = [
    path("", ResponseListCreateView.as_view(), name="responses"),
    path("<uuid:pk>/", ResponseDetailView.as_view(), name="response-detail"),
]
