from django.urls import path

from .views import ConfigEnumsView, health_check

urlpatterns = [
    path("config/enums/", ConfigEnumsView.as_view(), name="config-enums"),
    path("health/", health_check, name="health-check"),
]
