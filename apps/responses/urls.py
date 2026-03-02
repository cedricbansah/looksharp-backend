from django.urls import path

from .views import ResponseListCreateView

urlpatterns = [
    path("", ResponseListCreateView.as_view(), name="responses"),
]
