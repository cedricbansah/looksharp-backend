from django.urls import path

from .views import AdminResponseDetailView, AdminResponseListView

urlpatterns = [
    path("responses/", AdminResponseListView.as_view(), name="admin-responses"),
    path("responses/<uuid:pk>/", AdminResponseDetailView.as_view(), name="admin-response-detail"),
]
