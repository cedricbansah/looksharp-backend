from django.urls import path

from .views import VerificationListCreateView

urlpatterns = [
    path("", VerificationListCreateView.as_view(), name="verifications"),
]
