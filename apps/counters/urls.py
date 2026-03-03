from django.urls import path

from .views import AdminCounterRebuildView, AdminDashboardView

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("counters/rebuild/", AdminCounterRebuildView.as_view(), name="admin-counter-rebuild"),
]
