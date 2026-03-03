from django.urls import path

from .views import (
    AdminOfferListCreateView,
    AdminOfferPosterUploadView,
    AdminOfferUpdateDeleteView,
)

urlpatterns = [
    path("offers/", AdminOfferListCreateView.as_view(), name="admin-offers"),
    path("offers/<str:offer_id>/", AdminOfferUpdateDeleteView.as_view(), name="admin-offers-detail"),
    path(
        "offers/<str:offer_id>/upload-poster/",
        AdminOfferPosterUploadView.as_view(),
        name="admin-offers-upload-poster",
    ),
]
