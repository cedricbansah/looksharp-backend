from django.urls import path

from .views import MeView, WelcomeBonusClaimView

urlpatterns = [
    path("me/", MeView.as_view(), name="users-me"),
    path("me/welcome-bonus/claim/", WelcomeBonusClaimView.as_view(), name="users-welcome-bonus-claim"),
]
