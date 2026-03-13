from django.urls import path

from .views import (
    AdminOfferCategoryListCreateView,
    AdminOfferCategoryUpdateDeleteView,
    AdminOfferListCreateView,
    AdminOfferPosterUploadView,
    AdminOfferUpdateDeleteView,
)

urlpatterns = [
    path(
        "offer-categories/",
        AdminOfferCategoryListCreateView.as_view(),
        name="admin-offer-categories",
    ),
    path(
        "offer-categories/<str:category_id>/",
        AdminOfferCategoryUpdateDeleteView.as_view(),
        name="admin-offer-categories-detail",
    ),
    path("offers/", AdminOfferListCreateView.as_view(), name="admin-offers"),
    path("offers/<str:offer_id>/", AdminOfferUpdateDeleteView.as_view(), name="admin-offers-detail"),
    path(
        "offers/<str:offer_id>/upload-poster/",
        AdminOfferPosterUploadView.as_view(),
        name="admin-offers-upload-poster",
    ),
]
