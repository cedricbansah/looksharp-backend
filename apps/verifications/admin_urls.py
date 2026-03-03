from django.urls import path

from .views import (
    AdminCreateRecipientView,
    AdminVerificationApproveView,
    AdminVerificationListView,
    AdminVerificationRejectView,
)

urlpatterns = [
    path("verifications/", AdminVerificationListView.as_view(), name="admin-verifications"),
    path(
        "verifications/<uuid:verification_id>/approve/",
        AdminVerificationApproveView.as_view(),
        name="admin-verifications-approve",
    ),
    path(
        "verifications/<uuid:verification_id>/reject/",
        AdminVerificationRejectView.as_view(),
        name="admin-verifications-reject",
    ),
    path(
        "verifications/<uuid:verification_id>/create-recipient/",
        AdminCreateRecipientView.as_view(),
        name="admin-verifications-create-recipient",
    ),
]
