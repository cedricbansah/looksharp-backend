from django.urls import path

from .views import AdminResponseListView

urlpatterns = [
    path("responses/", AdminResponseListView.as_view(), name="admin-responses"),
]
