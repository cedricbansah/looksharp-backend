from django.urls import path

from .views import (
    AdminClientListCreateView,
    AdminClientLogoUploadView,
    AdminClientUpdateDeleteView,
)

urlpatterns = [
    path("clients/", AdminClientListCreateView.as_view(), name="admin-clients"),
    path("clients/<str:client_id>/", AdminClientUpdateDeleteView.as_view(), name="admin-clients-detail"),
    path(
        "clients/<str:client_id>/upload-logo/",
        AdminClientLogoUploadView.as_view(),
        name="admin-clients-upload-logo",
    ),
]
