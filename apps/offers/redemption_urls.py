from django.urls import path

from .views import RedemptionListCreateView

urlpatterns = [
    path("", RedemptionListCreateView.as_view(), name="redemptions"),
]
